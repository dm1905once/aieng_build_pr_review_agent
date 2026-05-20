import os
import re
import sys

import dotenv
from github import Github
from github import GithubException
from hstest import StageTest, CheckResult, dynamic_test, TestedProgram

dotenv.load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import repo_url


class AgentTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    @dynamic_test
    def check_url_set(self):
        if repo_url == "":
            return CheckResult.wrong("The URL in main.py is not set.")
        return CheckResult.correct()

    @dynamic_test(time_limit=0)
    def check_repo(self):
        if self.g is None:
            return CheckResult.wrong("GitHub token is not set. in environment")

        repo_name = repo_url.split('/')[-1].replace('.git', '')  # Remove .git if present
        username = repo_url.split('/')[-2]
        full_repo_name = f"{username}/{repo_name}"

        try:
            # Call get_repo once and store the result
            repo = self.g.get_repo(full_repo_name)

            if repo.private:
                return CheckResult.wrong("The repository is private. Make sure it's public.")

            expected_files = {"README.md", ".gitignore", "app/models.py", "app/tests/test_views.py",
                              "pyproject.toml", "CONTRIBUTING.md", "app/views.py", "recipes/settings.py",
                              ".github/workflows/ci.yml", "manage.py"}

            repo_contents = set()

            def check_directory_contents(contents_url, path=""):
                contents = repo.get_contents(path)
                for content in contents:
                    if content.type == "dir":
                        check_directory_contents(contents_url, content.path)
                    else:
                        repo_contents.add(content.path)

            check_directory_contents(repo.get_contents(""))

            missing_files = expected_files - repo_contents
            if missing_files:
                missing_files_str = ', '.join(missing_files)
                return CheckResult.wrong(
                    f"The repository is missing the following expected file(s): {missing_files_str}")

            pull_requests = repo.get_pulls(state="open", sort="created")
            if pull_requests.totalCount == 0:
                return CheckResult.wrong("No open pull requests found — please open one with the specified changes "
                                         "to app/models.py and app/serializers.py in a new branch. ")
            latest_pull = pull_requests[0]
            modified_files = [f.filename for f in latest_pull.get_files()]
            required = {"app/serializers.py", "app/models.py"}
            present = set(modified_files)
            missing_required = required - present
            if missing_required:
                missing_str = ', '.join(missing_required)
                return CheckResult.wrong(
                    f"The PR must modify the following files: {missing_str}. Found: {modified_files}")

            pr_number = latest_pull.number
            program = TestedProgram("main.py")
            program.start()
            output = program.execute(f"Write a review for PR number {pr_number}")

            if not re.search(r"Current agent:\s*.*Agent", output):
                return CheckResult.wrong(
                    "Agent name declaration missing or malformed. Did you invoke the agent as instructed?")

            if not re.search(r"Selected tools:\s*\[[^\]]+\]", output):
                return CheckResult.wrong("No selected tools list found or it is empty.")

            tool_calls = re.findall(r"Calling selected tool: (\w+), with arguments: (\{.*?\})", output)
            if len(tool_calls) < 1:
                return CheckResult.wrong("No tool invocation logs found.")

            if not re.search(r"Output from tool: \{[^}]*'title': '[^']+'", output):
                return CheckResult.wrong("PR details output missing title field.")
            if not re.search(r"'body': '[^']+'", output):
                return CheckResult.wrong("PR details output missing body field.")
            if not re.search(r"Output from tool: \[\{[^}]*'filename': '[^']+'", output):
                return CheckResult.wrong("Changed files output missing file entries. Check your changed files tool. ")

            if len(tool_calls) < 5:
                return CheckResult.wrong("Expected multiple tool invocation logs, found fewer.")

            if not re.search(r"Selected tools:\s*\['handoff'\]", output):
                return CheckResult.wrong("Hand-off not found. Ensure your agents are passing control to each other.")
            if not re.search(
                    r"Calling selected tool: handoff, with arguments:\s*\{[^}]*'to_agent':\s*'CommentorAgent'",
                    output
            ):
                return CheckResult.wrong("Handoff call to CommentorAgent is missing. Did you properly orchestrate the"
                                         "workflow with AgentWorkflow?")

            if not re.search(
                    r"Calling selected tool: handoff, with arguments:\s*\{[^}]*'to_agent':\s*'ContextAgent'",
                    output
            ):
                return CheckResult.wrong("Handoff call to ContextAgent is missing. Did you properly orchestrate the"
                                         "workflow with AgentWorkflow?")

            if not re.search(
                    r"Output from tool: Agent CommentorAgent is now handling the request due to the following reason:",
                    output
            ):
                return CheckResult.wrong(
                    "Handoff tool’s output to CommentorAgent is missing. Did you properly orchestrate the"
                    "workflow with AgentWorkflow?")
            if not re.search(
                    r"Output from tool: Agent ContextAgent is now handling the request due to the following reason:",
                    output
            ):
                return CheckResult.wrong(
                    "Handoff tool’s output to ContextAgent is missing. Did you properly orchestrate the"
                    "workflow with AgentWorkflow?")

            agents = re.findall(r"Current agent:\s*(\w+)", output)
            unique_agents = set(agents)
            needed = {'ContextAgent', 'CommentorAgent'}
            if not needed.issubset(unique_agents):
                return CheckResult.wrong(
                    f"Expected Current agent declarations for both ContextAgent and CommentorAgent; "
                    f"found: {unique_agents}"
                )

            return CheckResult.correct()

        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("The repository does not exist or is private.")
            else:
                return CheckResult.wrong(
                    f"An error occurred while accessing the repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"An unexpected error occurred: {e}")


if __name__ == '__main__':
    AgentTest().run_tests()
