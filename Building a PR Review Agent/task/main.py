import dotenv
import os
import asyncio
from github import Github
from github import GithubException
from github import Auth
from llama_index.llms.openai import OpenAI
from llama_index.core.tools import FunctionTool
from llama_index.core.agent.workflow import ReActAgent, AgentOutput, ToolCallResult
from llama_index.core.workflow import Context
from llama_index.core.prompts import RichPromptTemplate

# == Initializations ==
dotenv.load_dotenv()

# Model
llm = OpenAI(
    model="gpt-4o-mini",
    api_key=os.getenv("LITELLM_API_KEY"),
    api_base=os.getenv("LITELLM_BASE_URL"),
)

# Github
git = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN"))) if os.getenv("GITHUB_TOKEN") else None
repo_url = "https://github.com/dm1905once/recipes-api.git"
repo_name = repo_url.split('/')[-1].replace('.git', '')
username = repo_url.split('/')[-2]
full_repo_name = f"{username}/{repo_name}"


# == Functions ==
def get_pr_details(pull_number:int) -> str:
    """
    Provides details about a pull request (pr) given a pull request number
    :param pull_number: pull request number
    :return: dictionary containing details of the pull request
    """
    pr_details = {}
    try:
        repo = git.get_repo(full_repo_name)
        pull = repo.get_pull(pull_number)
        pr_details["repo_name"] = full_repo_name
        pr_details["author"] = pull.user.login
        pr_details["title"] = pull.title
        pr_details["body"] = pull.body
        pr_details["diff_url"] = pull.diff_url
        commit_SHAs = []
        commits = pull.get_commits()
        for c in commits:
            commit_SHAs.append(c.sha)
        pr_details["commit_shas"] = commit_SHAs
    except GithubException as e:
        pr_details['error'] = "Unable to retrieve PR details"
    return str(pr_details)

def get_file_contents(path:str) -> str:
    """
    Provides contents of a file given a path
    :param path: Path of the file within the repository
    :return: File contents
    """
    try:
        repo = git.get_repo(full_repo_name)
        file_content = repo.get_contents(path).decoded_content.decode('utf-8')
        return file_content
    except GithubException as e:
        return "{'error': 'Unable to retrieve file contents'}"

def get_pr_commit_details(commit_sha:str) -> list:
    """
    Provides details about a pull request (pr) given a commit sha
    :param commit_sha: SHA of the commit to retrieve details for
    :return: list containing details of the pull request
    """
    try:
        repo = git.get_repo(full_repo_name)
        commit = repo.get_commit(commit_sha)
        changed_files: list[dict[str, Any]] = []
        for f in commit.files:
            changed_files.append({
                "filename": f.filename,
                "status": f.status,
                "additions": f.additions,
                "deletions": f.deletions,
                "changes": f.changes,
                "patch": f.patch,
            })
        return changed_files
    except GithubException as e:
        return [{'error': 'Unable to retrieve file contents'}]

# == Tool ==
tools = [
    FunctionTool.from_defaults(get_pr_details),
    FunctionTool.from_defaults(get_file_contents),
    FunctionTool.from_defaults(get_pr_commit_details)
]

# == Agent ==
agent = ReActAgent(
    llm=llm,
    name="PR Review Agent",
    tools=tools
)

# == Context ==
context = Context(agent)

# == Execution ==
async def main():
    query = input().strip()
    prompt = RichPromptTemplate(query)
    handler = agent.run(prompt.format(), ctx=context)

    current_agent = None
    async for event in handler.stream_events():
        if hasattr(event, "current_agent_name") and event.current_agent_name != current_agent:
            current_agent = event.current_agent_name
            print(f"Current agent: {current_agent}")
        elif isinstance(event, AgentOutput):
            if event.response.content:
                print(event.response.content)
        elif isinstance(event, ToolCallResult):
            print(f"Output from tool: {event.tool_output}")

if __name__ == "__main__":
    asyncio.run(main())
    git.close()
