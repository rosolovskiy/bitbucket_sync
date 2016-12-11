__author__ = 'Alexey Rosolovskiy'
__version__ = '0.0.1'

import sys
import argparse
import time
import os
import subprocess
import multiprocessing

import requests


class ApiClient(object):
    """
    Bitbucket API v2.0 client which provides methods
    for getting user and team repositories
    """

    api_user = "https://api.bitbucket.org/2.0/user"
    api_user_repositories = "https://api.bitbucket.org/2.0/users/{username}/repositories"
    api_teams = "https://api.bitbucket.org/2.0/teams"
    api_team_repositories = "https://api.bitbucket.org/2.0/repositories/{team}"

    def __init__(self, auth_helper):
        self.auth = auth_helper

    def get_username(self):
        """
        Returns username related to API client token
        """
        h = {}
        self.auth.set_auth_header(h)
        r = requests.get(self.api_user, headers=h)
        if r.status_code == requests.codes.ok:
            d = r.json()
            return d["username"]
        else:
            r.raise_for_status()

    def get_teams(self):
        """
        Returns list of teams where API client has access to
        """
        h = {}
        self.auth.set_auth_header(h)
        r = requests.get(self.api_teams, params={"role": "member"}, headers=h)
        if r.status_code == requests.codes.ok:
            d = r.json()
            # page = d["page"]
            page_len = d["pagelen"]
            size = d["size"]
            assert size <= page_len  # TODO: support pagination
            return [t["username"] for t in d["values"]]
        else:
            r.raise_for_status()

    def _fetch_multi_page_response(self, first_page_url):
        h = {}
        self.auth.set_auth_header(h)
        r = requests.get(first_page_url,
                         headers=h)
        if r.status_code == requests.codes.ok:
            d = r.json()
            pages = [d]
            page_len = d["pagelen"]
            size = d["size"]
            if size >= page_len and "next" in d:
                while "next" in d:
                    r = requests.get(d["next"], headers=h)
                    d = r.json()
                    pages.append(d)
            return pages
        else:
            r.raise_for_status()

    def _get_user_repositories(self, username):
        pages = self._fetch_multi_page_response(self.api_user_repositories.format(username=username))
        repo = (l["links"]["clone"] for p in pages for l in p["values"] if l["scm"] == "git")  # TODO: hg
        return [href["href"] for a in repo for href in a if href["name"] == "ssh"]

    def _get_team_repositories(self, team):
        pages = self._fetch_multi_page_response(self.api_team_repositories.format(team=team))
        repo = (l["links"]["clone"] for p in pages for l in p["values"] if l["scm"] == "git")  # TODO: hg
        return [href["href"] for a in repo for href in a if href["name"] == "ssh"]

    def get_repositories(self, username=None, teams=tuple()):
        """
        Returns distinct tuple of repositories that given
        user and teams has access to if client API
        token has access to them as well
        """
        repositories = []
        if username:
            tuples = ((username, r) for r in self._get_user_repositories(username))
            repositories.extend(tuples)
        for t in teams:
            tuples = ((t, r) for r in self._get_team_repositories(t))
            repositories.extend(tuples)
        return tuple(set(repositories))


class Auth(object):
    """
    Helper class that handles authorization credentials and
    sets authorization header for API HTTP Request headers.
    If token is not gotten yet, then requests it from API.

    Uses Client Credentials Grant (OAuth2.0) way to get a token.
    See: https://tools.ietf.org/html/rfc6749#section-4.4
    See: https://developer.atlassian.com/bitbucket/api/2/reference/meta/authentication
    """

    token_url = "https://bitbucket.org/site/oauth2/access_token"

    def __init__(self, client_id, secret):
        self.client_id = client_id
        self.secret = secret
        self.auth_token = None
        self.refresh_token = None
        self.auth_token_expires_at = 0
        self._token_reset_threshold = 600  # seconds

    def _reset_token_if_expired(self):
        """
        :return: True if token was reset
        """
        now = int(time.time())
        if self.auth_token_expires_at + self._token_reset_threshold <= now:
            self.auth_token = None
            self.auth_token_expires_at = 0
            # TODO: refresh token here, now just request another one
            return True
        else:
            return False

    def set_auth_header(self, headers):
        self._reset_token_if_expired()
        if not self.auth_token:
            self._request_auth_token()
        headers["Authorization"] = "Bearer {0!s}".format(self.auth_token)

    def _request_auth_token(self):
        r = requests.post(self.token_url,
                          data={"grant_type": "client_credentials"},
                          auth=(self.client_id, self.secret))
        if r.status_code == requests.codes.ok:
            d = r.json()
            self.auth_token = d["access_token"]
            self.refresh_token = d["refresh_token"]
            self.auth_token_expires_at = int(time.time()) + d["expires_in"]
            return True
        else:
            return False


def owner_directory(base_dir, repo_tuple):
    d = os.path.join(base_dir, repo_tuple[0])
    return os.path.exists(d), d


def apply_filters(repositories, include_owners=(), exclude_owners=()):
    if repositories and include_owners or exclude_owners:
        filtered = []
        for r in repositories:
            if r[0] in exclude_owners:
                continue
            if include_owners:
                if r[0] in include_owners:
                    filtered.append(r)
            else:
                filtered.append(r)
        return tuple(filtered)
    else:
        return repositories


def handle_repo(base_dir, owner, clone_url):
    dir_exists, dir_path = owner_directory(base_dir, (owner, clone_url))
    if not dir_exists:
        os.makedirs(dir_path, 0o744)
    project_name = os.path.basename(clone_url)
    if project_name.endswith(".git"):
        project_name = project_name[:-4]
    project_dir = os.path.join(dir_path, project_name)
    if os.path.exists(project_dir):
        code = subprocess.call(["git", "-C", project_dir, "pull", "--recurse-submodules=yes"])
    else:
        code = subprocess.call(["git", "-C", dir_path, "clone", "--recursive", clone_url])
    return owner, clone_url, project_dir, code == 0, code


def print_scm_result(result):
    print result


def main(argv):
    script_path, args = argv[0], argv[1:]
    parser = argparse.ArgumentParser(description='Downloads all user repositories to defined destination directory.')
    parser.add_argument('destination', metavar='/home/user/bitbucket_backup/', type=str,
                        help='Directory where to clone repositories to.')
    parser.add_argument('client_key', help="OAuth2 client key")
    parser.add_argument('client_secret', help="OAuth2 client secret")
    parser.add_argument('-i', '--include-owners', metavar='my_company', nargs='*', default=[],
                        help='List of repo owners (team or user) to sync, others will be ignored')
    parser.add_argument('-x', '--exclude-owners', metavar='my_user', nargs='*', default=[],
                        help='List of repo owners (team or user) to not sync, others will be synced')
    parsed = parser.parse_args(args)
    a = Auth(parsed.client_key, parsed.client_secret)
    cli = ApiClient(a)
    username = cli.get_username()
    teams = cli.get_teams()
    repositories = cli.get_repositories(username, tuple(teams))
    pool = multiprocessing.Pool()
    for r in apply_filters(repositories, parsed.include_owners, parsed.exclude_owners):
        pool.apply_async(handle_repo, (parsed.destination, r[0], r[1]), callback=print_scm_result)
    pool.close()
    pool.join()


if __name__ == "__main__":
    main(sys.argv)
