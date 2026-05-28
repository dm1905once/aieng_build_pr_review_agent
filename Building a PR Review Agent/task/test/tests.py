import os
import sys

import dotenv
import yaml
from github import Github
from github import GithubException
from hstest import StageTest, CheckResult, dynamic_test

dotenv.load_dotenv()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from main import repo_url


class AgentTest(StageTest):
    g = Github(os.getenv("GITHUB_TOKEN")) if os.getenv("GITHUB_TOKEN") else Github()

    repo_name = repo_url.split('/')[-1].replace('.git', '')
    username = repo_url.split('/')[-2]
    full_repo_name = f"{username}/{repo_name}"
    repo = g.get_repo(full_repo_name)
    pull_requests = repo.get_pulls(state="open", sort="created")

    @classmethod
    def handle_github_exception(cls, e):
        if e.status == 404:
            return CheckResult.wrong("The requested resource does not exist.")
        elif e.status == 403:
            return CheckResult.wrong("Access to the resource is forbidden or rate limit exceeded.")
        elif e.status == 401:
            return CheckResult.wrong("Authentication is required or has failed.")
        else:
            return CheckResult.wrong(
                f"An error occurred while accessing the GitHub repository: {e.data.get('message', 'No error message')}")

    @dynamic_test
    def check_url_set(self):
        if repo_url == "":
            return CheckResult.wrong("The URL in main.py is not set.")
        return CheckResult.correct()

    @dynamic_test(time_limit=0)
    def check_repo(self):
        if self.g is None:
            return CheckResult.wrong("GitHub token is not set. in environment")
        try:
            if self.repo.private:
                return CheckResult.wrong("The repository is private. Make sure it's public.")

            expected_files = {"README.md", ".gitignore", "app/models.py", "app/tests/test_views.py",
                              "pyproject.toml", "CONTRIBUTING.md", "app/views.py", "recipes/settings.py",
                              "manage.py", "agent.py", ".github/workflows/ci.yml"
                              }

            repo_contents = set()

            def check_directory_contents(contents_url, path=""):
                contents = self.repo.get_contents(path)
                for content in contents:
                    if content.type == "dir":
                        check_directory_contents(contents_url, content.path)
                    else:
                        repo_contents.add(content.path)

            check_directory_contents(self.repo.get_contents(""))

            missing_files = expected_files - repo_contents
            if missing_files:
                missing_files_str = ', '.join(missing_files)
                return CheckResult.wrong(
                    f"The repository is missing the following expected file(s): {missing_files_str}")

            if self.pull_requests.totalCount == 0:
                return CheckResult.wrong("No open pull requests found — please open one with the specified changes "
                                         "to app/models.py and app/serializers.py in a new branch. ")
            latest_pull = self.pull_requests[0]
            modified_files = [f.filename for f in latest_pull.get_files()]
            required = {"app/serializers.py", "app/models.py"}
            present = set(modified_files)
            missing_required = required - present
            if missing_required:
                missing_str = ', '.join(missing_required)
                return CheckResult.wrong(
                    f"The PR must modify the following files: {missing_str}. Found: {modified_files}")

            return CheckResult.correct()

        except GithubException as e:
            if e.status == 404:
                return CheckResult.wrong("The repository does not exist or is private.")
            else:
                return CheckResult.wrong(
                    f"An error occurred while accessing the repository: {e.data.get('message', 'No error message')}")
        except Exception as e:
            return CheckResult.wrong(f"An unexpected error occurred: {e}")

    @dynamic_test
    def check_script_file_contents(self):
        try:
            contents = self.repo.get_contents("agent.py")
            if not contents:
                return CheckResult.wrong("The file 'agent.py' does not exist.")
            if not contents.decoded_content:
                return CheckResult.wrong("The file 'agent.py' is empty.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_main_file_exists(self):
        try:
            files = self.repo.get_contents(".github/workflows")
            main_yaml_file_exists = any(
                file.path == ".github/workflows/ci.yml" or file.path == ".github/workflows/ci.yaml" for
                file in files)
            if not main_yaml_file_exists:
                return CheckResult.wrong(f"The ci.yml file does not exist in the .github/workflows/ directory.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_manifest(self):
        try:
            contents = self.repo.get_contents(".github/workflows/ci.yml") or self.repo.get_contents(
                ".github/workflows/ci.yaml")

            workflow_file = contents.decoded_content.decode()
            new_workflow = yaml.load(workflow_file, Loader=yaml.BaseLoader)

            jobs = new_workflow.get("jobs")
            if not jobs:
                return CheckResult.wrong("The workflow does not have a job.")

            job_name, job = next(iter(jobs.items()), (None, None))

            if not job or job.get("runs-on") != "ubuntu-latest":
                return CheckResult.wrong("The job does not run on 'ubuntu-latest' runner or is missing.")

            if not any(job.get("permissions")):
                return CheckResult.wrong("The job does not have permissions. Did you modify the original workflow?")

            steps = job.get("steps", [])

            expected_steps = {
                "checkout_repository": r"actions/checkout@v",
                "set_up_python": "actions/setup-python@v",
                "run_the_agent": "poetry run python agent.py $"
            }
            for step_name, expected_value in expected_steps.items():
                if not any(step.get("run", "").startswith(expected_value) or step.get("uses", "").startswith(
                        expected_value) for step in steps):
                    return CheckResult.wrong(f"The job does not have a step to {step_name.replace('_', ' ')}.")
            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test
    def check_workflow_run_on_prs(self):
        try:
            latest_workflow_run = list(self.repo.get_workflow_runs().get_page(0))[0]
            if latest_workflow_run.event != "pull_request":
                return CheckResult.wrong(f"The latest workflow run was not triggered by an PR event.")
            if latest_workflow_run.conclusion != "success":
                return CheckResult.wrong(f"The latest workflow run did not succeed.")

            return CheckResult.correct()
        except GithubException as e:
            return self.handle_github_exception(e)
        except Exception as e:
            return CheckResult.wrong(f"Something went wrong. Encountered: {e}")

    @dynamic_test(time_limit=0)
    def test4_check_latest_pr_comment(self):
        if self.pull_requests.totalCount == 0:
            return CheckResult.wrong("No open pull requests found — please open one with the specified changes "
                                     "to app/models.py and app/serializers.py in a new branch. ")
        latest_pull = self.pull_requests[0]
        pr_number = latest_pull.number
        pr = self.repo.get_pull(pr_number)

        comments = pr.get_issue_comments()
        reviews = pr.get_reviews()

        if comments.totalCount == 0:
            return CheckResult.wrong("Test results from workflow not found. Did you modify the original code?")
        if reviews.totalCount == 0:
            return CheckResult.wrong(
                "No review comments found. Ensure that your agent is posting the comments back to GitHub. ")

        found = any(review.user.login == "github-actions[bot]" for review in reviews)
        if not found:
            return CheckResult.wrong(
                "No review was posted by GitHub Actions. Ensure your workflow is working as expected.")

        return CheckResult.correct()


if __name__ == '__main__':
    AgentTest().run_tests()
