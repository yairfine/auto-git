import os
import sys
import json
import time
import asyncio
import requests
from argparse import ArgumentParser
from pathlib import Path
# ? https://www.devdungeon.com/content/working-git-repositories-python
from git import Repo
import git
from pprint import pprint
import subprocess

INTERVAL_SECONDS = 7  # 60 in deployment version

DESCRIPTION = "Track file and automatic push to remote github repository."
EPILOG = "For more information, visit the project page on: https://github.com/yairfine/auto-git"
HELP_FILE_PATH = "The path to the file you want to git."
HELP_START_TRACK = "Sets the program to track an existing repo and file"
HELP_NEW_TRACK = "Sets the program create a new track for a given file"
HELP_FIRST_CONFIG = "Sets the program to first-config mode"
METAVAR_FILE_PATH = "<file_path>"

ERR_PAT_EXISTS = "It's seems like you already configured this system, try to run again with -n/-s flag"
ERR_CREATE_REMOTE = ' ~~ Error creating remote repo ~~ '
ERR_SETTINGS_LOCAL_EXISTS = "It's seems like you already initiated this directory, try to run again with -s flag"
ERR_PARSE_JSON = " ~~ Error parsing json ~~ "
ERR_STATUS_CODE = "Respone code is not ok - {}"

MSG_END_NEW_TRACK = "Done preparing for a new track"
MSG_START_TRACKING = "Started tracking changes on file '{}'"
MSG_EXIT_TRACKING = "To stop: press Ctrl+C and wait a few seconds"
MSG_END_TRACKING = "Tracking session has ended"
MSG_CHANGE_RECORDED = "A change was recorded in {}"
MSG_COMMIT = "commit no.{} - {}"

PROMPT_SSH_PAT_CONFIG = """
Make sure you have Git installed (version > 1.5)
2.  Open: Git-Bash
3.  Run: ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
4.  Press enter: Enter a file in which to save the key (/c/Users/you/.ssh/id_rsa):[Press enter]
5.  Press enter: Enter passphrase (empty for no passphrase): [Press enter] (no password needed)
6.  Press enter: [Press enter again] (no password needed)
7.  Run: eval $(ssh-agent -s)
8.  Run: ssh-add ~/.ssh/id_rsa
9.  Run: clip < ~/.ssh/id_rsa.pub   #Copies the contents of the id_rsa.pub file to your clipboard
10. Open: github.com
11. Click: In upper-right corner click profile photo -> settings
12. Click: SSH and GPG keys (side menu)
13. Click: New SSH key or Add SSH key.
14. Title field: write 'auto-git-ssh'
15. Key field: paste your key
16. Click: Add SSH key
17. Click: Developer settings (side menu)
18. Click: Personal access tokens
19. Click: Generate new token
20. Note field: write 'auto-git-pat'
21. Select scopes: 'repo', 'read:user', 'user:email'
22. Click: Generate token
23. COPY!!!: copy the new token (with green V sign aside)
24. Paste: paste the token here and press enter:
"""
PROMPT_PAT = "Please enter your Private Accesses Token: "
PROMPT_REPO_NAME = "Please enter your new repository name: "

SETTINGS_DIR = Path.home() / 'auto-git-settings'
SETTINGS_FILE_GLOBAL = SETTINGS_DIR / 'auto_git_settings_global.txt'
# SETTINGS_PAT = SETTINGS_DIR / 'pat.txt'
# SETTINGS_USER = SETTINGS_DIR / 'user.txt'

API_BASE_URL = 'https://api.github.com'


def initiate_settings_global_dir(settings_dir_path):

    try:
        settings_dir_path.mkdir()
        SETTINGS_FILE_GLOBAL.touch(exist_ok=False)

    except FileExistsError:
        print(ERR_PAT_EXISTS)
        sys.exit()


def retrieve_pat():
    pat = input(PROMPT_PAT)
    return pat


def get_endpoint(end_point, pat):
    url = f"{API_BASE_URL}{end_point}"

    headers = {
        "Authorization": f"token {pat}"
    }

    r = requests.get(url, headers=headers)

    if not r.ok:
        print(ERR_STATUS_CODE.format(r.status_code))
        sys.exit()

    try:
        response_dict = json.loads(r.text)
    except:
        print(ERR_PARSE_JSON)
        sys.exit()

    return response_dict


def post_endpoint(end_point, pat, json_data):
    url = f"{API_BASE_URL}{end_point}"

    headers = {
        "Authorization": f"token {pat}"
    }

    r = requests.post(url, headers=headers, json=json_data)

    if r.status_code != 201:
        print(ERR_CREATE_REMOTE)
        print(ERR_STATUS_CODE.format(r.status_code))
        sys.exit()

    try:
        response_dict = json.loads(r.text)
    except:
        print(ERR_CREATE_REMOTE)
        sys.exit()

    return response_dict


async def push_changes(file_to_track):
    dir_path = file_to_track.parent
    settings_file = dir_path / 'auto_git_settings.txt'
    settings_dict = json.loads(settings_file.read_text())

    print(MSG_START_TRACKING.format(settings_dict['file_name']))
    print(MSG_EXIT_TRACKING)

    repo = Repo(dir_path)

    while True:
        await asyncio.sleep(INTERVAL_SECONDS)

        if repo.is_dirty(untracked_files=True):

            repo.git.add('.')
            repo.index.commit(MSG_COMMIT.format(settings_dict['count_commits'],
                                                time.asctime(time.localtime())))
            repo.remotes.origin.push()

            settings_dict['count_commits'] += 1
            settings_json = json.dumps(settings_dict)
            settings_file.write_text(settings_json)
            print(MSG_CHANGE_RECORDED.format(time.asctime(time.localtime())))


def start_track(raw_file_path):
    file_to_track = Path(raw_file_path)

    loop = asyncio.get_event_loop()
    try:
        asyncio.ensure_future(push_changes(file_to_track))
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print(MSG_END_TRACKING)
        # maybe update some settings here?
        loop.close()

    # * todo create a time based loop, for checking every minuet if a file was changed
    # * todo add, commit, and push changes
    # * todo add count the number of the repos
    # todo add in json all the files we track


def initiate_settings_local_dir(settings_file, readme_file, gitignore_file):
    try:
        settings_file.touch(exist_ok=False)
        readme_file.touch(exist_ok=False)
        gitignore_file.touch(exist_ok=False)

    except FileExistsError:
        print(ERR_SETTINGS_LOCAL_EXISTS)
        sys.exit()


def write_settings_local(settings_file, settings_json, readme_file, readme,
                         gitignore_file, ignores):
    settings_file.write_text(settings_json)
    readme_file.write_text(readme)
    gitignore_file.write_text(ignores)


def first_init_add_commit_push(dir_path, settings_dict_local):
    new_repo = Repo.init(path=dir_path, mkdir=False)

    new_repo.git.add('.')
    new_repo.index.commit('Initial commit.')

    new_repo.create_head('master').checkout()

    try:
        origin = new_repo.create_remote(
            'origin', url=settings_dict_local['ssh_url'])
    except:
        print(ERR_CREATE_REMOTE)
        sys.exit()

    new_repo.git.push("--set-upstream", origin, new_repo.head.ref)


def new_track(raw_file_path):
    file_to_track = Path(raw_file_path)
    dir_path = file_to_track.parent
    settings_file = dir_path / 'auto_git_settings.txt'
    readme_file = dir_path / 'README.md'
    gitignore_file = dir_path / '.gitignore'

    initiate_settings_local_dir(settings_file, readme_file, gitignore_file)

    repo_name = input(PROMPT_REPO_NAME)

    json_data = {
        "name": f"{repo_name}",
        "private": "true"
    }

    settings_dict_global = json.loads(SETTINGS_FILE_GLOBAL.read_text())

    response_dict = post_endpoint(
        "/user/repos", settings_dict_global['PAT'], json_data)

    settings_dict_local = {
        "file_name": f"{file_to_track.name}",
        "repo_name": f"{repo_name}",
        "ssh_url": f"{response_dict['ssh_url']}",
        "https_url": f"{response_dict['clone_url']}",
        "count_commits": 1
    }

    write_settings_local(settings_file, json.dumps(settings_dict_local),
                         gitignore_file, "auto_git_settings.txt",
                         readme_file, f"# {repo_name}")

    first_init_add_commit_push(dir_path, settings_dict_local)

    print(MSG_END_NEW_TRACK)

    start_track(raw_file_path)

    # * create a dict to json and retrieve https://stackoverflow.com/questions/26745519/converting-dictionary-to-json
    # * create settings file with the repo name and repo ssh https URI
    # * todo touch README.md
    # * todo touch .gitignore file
    # * todo git init add commit
    # * todo create new ssh remote tracking branch
    # todo make sure that github is in known hosts
    # todo and than start_track()


def first_config():

    initiate_settings_global_dir(SETTINGS_DIR)

    pat = retrieve_pat()

    response_dict = get_endpoint("/user", pat)

    user_name = response_dict['login']

    response_dict = get_endpoint("/user/emails", pat)

    user_email = response_dict[0]['email']

    settings_dict_global = {
        "PAT": f"{pat}",
        "user_name": f"{user_name}",
        "user_email": f"{user_email}"
    }
    settings_json_global = json.dumps(settings_dict_global)
    SETTINGS_FILE_GLOBAL.write_text(settings_json_global)

    ret = subprocess.run(f"git config --global user.name {user_name}")
    ret = subprocess.run(f"git config --global user.email {user_email}")
    #todo - check the ret

    # todo add github to the list of known-hosts. handle it before pushes!

    # todo generate ssh key, store it on place, and copy the pass to ssh.txt

    # todo give instructions to copy the pat key to pat.txt

    # todo


def main():
    parser = ArgumentParser(description=DESCRIPTION, epilog=EPILOG)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-f', '--first-config',
                       action="store_true", help=HELP_FIRST_CONFIG)
    group.add_argument('-n', '--new-track', action="store",
                       type=str, help=HELP_NEW_TRACK, metavar=METAVAR_FILE_PATH)
    group.add_argument('-s', '--start-track', action="store",
                       type=str, help=HELP_START_TRACK, metavar=METAVAR_FILE_PATH)

    args = parser.parse_args()

    if args.start_track is not None:
        start_track(args.start_track)

    elif args.new_track is not None:
        new_track(args.new_track)

    elif args.first_config is not None:
        first_config()


if __name__ == "__main__":
    main()
