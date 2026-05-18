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
def get_pr_details(pull_id:int) -> str:
    pr_details = {}
    try:
        repo = git.get_repo(full_repo_name)
        pull = repo.get_pull(pull_id)
        pr_details['id'] = pull.id
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

print(get_pr_details(3))
