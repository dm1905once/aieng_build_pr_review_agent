import dotenv
import os
from github import Github
from github import Auth

# Initialize
dotenv.load_dotenv()
git = Github(auth=Auth.Token(os.getenv("GITHUB_TOKEN"))) if os.getenv("GITHUB_TOKEN") else None

repo_url = "https://github.com/dm1905once/recipes-api.git"
repo_name = repo_url.split('/')[-1].replace('.git', '')
username = repo_url.split('/')[-2]
full_repo_name = f"{username}/{repo_name}"

# Functions
def get_pr_details(id:int):
    if git is not None:
        repo = git.get_repo(full_repo_name)
        pull = repo.get_pull(id)
        print(pull.title)
    else:
        return None
    git.close()

get_pr_details(3)
#file_content = repo.get_contents("main.py").decoded_content.decode('utf-8')
#print(file_content)
