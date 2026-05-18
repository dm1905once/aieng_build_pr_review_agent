import dotenv
import os
from github import Github
from github import GithubException
from github import Auth

# Initialize
dotenv.load_dotenv()
git = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN"))) if os.getenv("GITHUB_TOKEN") else None

repo_url = "https://github.com/dm1905once/recipes-api.git"
repo_name = repo_url.split('/')[-1].replace('.git', '')
username = repo_url.split('/')[-2]
full_repo_name = f"{username}/{repo_name}"

# Functions
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
        git.close()
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
        return "{'error': 'Unable to retrieve file contents'}"


# print(get_pr_details(3))
# print(get_file_contents("README.md"))
# print(get_pr_commit_details("37c2f8e042bc874b1d497f299a7aee715ab5bb99"))