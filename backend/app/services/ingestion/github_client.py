import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from github import Github, GithubException
from app.core.logging import get_logger

logger = get_logger(__name__)


class GitHubClient:
    """Authenticated GitHub API client for decision artifact extraction."""

    def __init__(self, token: str):
        self.github = Github(token)

    async def _execute_with_retry(self, func, *args, **kwargs) -> Any:
        """Helper to run blocking PyGithub calls in a thread with exponential backoff on rate limits."""
        max_retries = 5
        backoff = 2.0
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(func, *args, **kwargs)
            except GithubException as e:
                # 403 is often rate limit (Secondary rate limit or Primary rate limit)
                # 429 is Too Many Requests
                if e.status in (403, 429) and (
                    attempt < max_retries - 1
                ):
                    logger.warning(
                        "GitHub API rate limit or conflict hit. Retrying...",
                        status=e.status,
                        attempt=attempt + 1,
                        backoff=backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(
                        "GitHub API error",
                        status=e.status,
                        message=e.data.get("message", str(e)),
                    )
                    raise
            except Exception as e:
                logger.error("Unexpected error calling GitHub API", error=str(e))
                raise

    async def get_repository(self, owner: str, name: str) -> Dict[str, Any]:
        """Return repository metadata: name, description, default_branch, url."""
        def _get_repo():
            repo = self.github.get_repo(f"{owner}/{name}")
            return {
                "name": repo.name,
                "owner": repo.owner.login,
                "description": repo.description,
                "default_branch": repo.default_branch,
                "url": repo.html_url,
            }
        return await self._execute_with_retry(_get_repo)

    async def extract_issues(
        self,
        owner: str,
        name: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract all issues (state='all').
        For each issue return:
          external_id, title, body, author, created_at, closed_at,
          labels (list of strings), comments (list of {author, body, created_at}),
          url, state
        """
        def _extract():
            repo = self.github.get_repo(f"{owner}/{name}")
            params = {"state": "all"}
            if since:
                params["since"] = since

            # Fetch issues. Note: PyGithub's get_issues gets both issues and PRs.
            issue_list = repo.get_issues(**params)
            extracted = []
            count = 0
            limit = 50 if not since else 200

            for issue in issue_list:
                if count >= limit:
                    break
                # Filter out PRs from issues list
                if issue.pull_request is not None:
                    continue

                comments = []
                if issue.comments > 0:
                    for comment in issue.get_comments():
                        comments.append({
                            "author": comment.user.login if comment.user else "ghost",
                            "body": comment.body or "",
                            "created_at": comment.created_at,
                        })

                extracted.append({
                    "external_id": str(issue.number),
                    "title": issue.title,
                    "body": issue.body or "",
                    "author": issue.user.login if issue.user else "ghost",
                    "created_at": issue.created_at,
                    "closed_at": issue.closed_at,
                    "labels": [label.name for label in issue.labels],
                    "comments": comments,
                    "url": issue.html_url,
                    "state": issue.state,
                })
                count += 1
            return extracted

        results = await self._execute_with_retry(_extract)
        logger.info("Extracted issues from GitHub", count=len(results), repo=f"{owner}/{name}")
        return results

    async def extract_pull_requests(
        self,
        owner: str,
        name: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract all PRs (state='all').
        For each PR return:
          external_id, title, body, author, created_at, merged_at, closed_at,
          labels, review_comments (list of {author, body, created_at}),
          changed_files (list of filenames), url, state, merged
        """
        def _extract():
            repo = self.github.get_repo(f"{owner}/{name}")
            # get_pulls doesn't accept since directly, we will query all and filter if needed
            pr_list = repo.get_pulls(state="all")
            extracted = []
            count = 0
            limit = 50 if not since else 200

            for pr in pr_list:
                if count >= limit:
                    break
                # Apply since filter if provided
                if since and pr.updated_at < since:
                    continue

                review_comments = []
                if pr.review_comments > 0:
                    for comment in pr.get_review_comments():
                        review_comments.append({
                            "author": comment.user.login if comment.user else "ghost",
                            "body": comment.body or "",
                            "created_at": comment.created_at,
                        })

                # Fetch changed files
                changed_files = [f.filename for f in pr.get_files()]

                extracted.append({
                    "external_id": str(pr.number),
                    "title": pr.title,
                    "body": pr.body or "",
                    "author": pr.user.login if pr.user else "ghost",
                    "created_at": pr.created_at,
                    "merged_at": pr.merged_at,
                    "closed_at": pr.closed_at,
                    "labels": [label.name for label in pr.labels],
                    "review_comments": review_comments,
                    "changed_files": changed_files,
                    "url": pr.html_url,
                    "state": pr.state,
                    "merged": pr.merged,
                })
                count += 1
            return extracted

        results = await self._execute_with_retry(_extract)
        logger.info("Extracted PRs from GitHub", count=len(results), repo=f"{owner}/{name}")
        return results

    async def extract_commits(
        self,
        owner: str,
        name: str,
        since: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Extract all commits.
        For each commit return:
          external_id (SHA), title (first line of message), body (rest of message),
          author, created_at, url, files_changed (list of filenames)
        Limit to 1000 most recent if no since date.
        """
        def _extract():
            repo = self.github.get_repo(f"{owner}/{name}")
            params = {}
            if since:
                params["since"] = since

            commit_list = repo.get_commits(**params)
            extracted = []

            # Paginate up to 1000 commits if no since date
            count = 0
            limit = 1000 if not since else 5000

            for commit in commit_list:
                if count >= limit:
                    break

                message = commit.commit.message or ""
                lines = message.split("\n", 1)
                title = lines[0]
                body = lines[1] if len(lines) > 1 else ""

                author = "unknown"
                if commit.author:
                    author = commit.author.login
                elif commit.commit.author:
                    author = commit.commit.author.name

                files = [f.filename for f in commit.files]

                extracted.append({
                    "external_id": commit.sha,
                    "title": title,
                    "body": body,
                    "author": author,
                    "created_at": commit.commit.committer.date,
                    "url": commit.html_url,
                    "files_changed": files,
                })
                count += 1
            return extracted

        results = await self._execute_with_retry(_extract)
        logger.info("Extracted commits from GitHub", count=len(results), repo=f"{owner}/{name}")
        return results

    async def extract_adrs(self, owner: str, name: str) -> List[Dict[str, Any]]:
        """
        Search for ADR markdown files in: docs/adr/, adr/, architecture/, docs/decisions/
        For each .md file found return:
          external_id (file path), title (filename), body (raw content), author='system',
          created_at (file last commit date), url
        """
        target_dirs = ["docs/adr", "adr", "architecture", "docs/decisions"]

        def _search_adr_dirs():
            repo = self.github.get_repo(f"{owner}/{name}")
            extracted = []

            for path in target_dirs:
                try:
                    contents = repo.get_contents(path)
                    # contents can be a list of ContentFile or a single ContentFile
                    if not isinstance(contents, list):
                        contents = [contents]

                    for file in contents:
                        if file.type == "file" and file.name.lower().endswith(".md"):
                            # Get raw text content
                            decoded_body = file.decoded_content.decode("utf-8")

                            # Get date of last commit modifying this file
                            commit_date = datetime.utcnow()
                            commits = repo.get_commits(path=file.path)
                            if commits.totalCount > 0:
                                commit_date = commits[0].commit.committer.date

                            extracted.append({
                                "external_id": file.path,
                                "title": file.name,
                                "body": decoded_body,
                                "author": "system",
                                "created_at": commit_date,
                                "url": file.html_url,
                            })
                except GithubException as e:
                    if e.status == 404:
                        # Directory does not exist, check the next one
                        continue
                    else:
                        logger.error("GitHub exception searching path", path=path, error=str(e))
                        raise
            return extracted

        results = await self._execute_with_retry(_search_adr_dirs)
        logger.info("Extracted ADRs from GitHub", count=len(results), repo=f"{owner}/{name}")
        return results
