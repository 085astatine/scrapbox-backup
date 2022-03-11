import logging
from ._backup import Backup, BackupStorage, DownloadedBackup
from ._env import Env
from ._git import Commit, CommitTarget, Git
from ._utility import format_timestamp


def commit(
        env: Env,
        logger: logging.Logger) -> None:
    git = env.git(logger=logger)
    storage = env.backup_storage()
    # check if the git repository exists
    if not git.exists():
        logger.error(f'git repository "{git.path}" does not exist')
        return
    # backup targets
    backup_targets = _backup_targets(storage, git, logger)
    # commit
    for target in backup_targets:
        logger.info(f'commit {format_timestamp(target.timestamp)}')
        # load backup
        backup = target.load(env.project, git.path)
        if backup is None:
            logger.info(
                    'failed to load backup'
                    f' {format_timestamp(target.timestamp)}')
            continue
        # sort pages
        backup.sort_pages(env.page_order)
        # commit
        _commit(git, backup, logger)


def _backup_targets(
        storage: BackupStorage,
        git: Git,
        logger: logging.Logger) -> list[DownloadedBackup]:
    # get latest backup timestamp
    latest = git.latest_commit_timestamp()
    logger.info(f'latest backup: {format_timestamp(latest)}')
    # find backup
    targets = [
            backup for backup in storage.backups()
            if latest is None or latest < backup.timestamp]
    return targets


def _commit(
        git: Git,
        backup: Backup,
        logger: logging.Logger) -> None:
    # load previous backup
    previous_backup = Backup.load(backup.project, git.path)
    previous_backup_files = set(
            previous_backup.save_files()
            if previous_backup is not None
            else [])
    # clear previous backup
    for previous_file in previous_backup_files:
        logger.debug(f'remove "{previous_file.as_posix()}"')
        previous_file.unlink()
    # copy backup
    backup_files = set(backup.save_files())
    backup.save()
    # commit target
    target = CommitTarget(
            added=sorted(backup_files - previous_backup_files),
            updated=sorted(backup_files & previous_backup_files),
            deleted=sorted(previous_backup_files - backup_files))
    # commit message
    message = Commit.message(
            backup.project,
            backup.timestamp,
            backup.info)
    # commit
    git.commit(
            target,
            message,
            timestamp=backup.timestamp)
