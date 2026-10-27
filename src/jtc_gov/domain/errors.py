class RepoError(Exception):
    """git の読み取りに失敗した(base がない、git が失敗した)。"""
