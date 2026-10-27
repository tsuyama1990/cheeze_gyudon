from jtc_gov.checks.d import check_d
from jtc_gov.checks.human_merge import human_merge
from jtc_gov.checks.k import check_k
from jtc_gov.checks.pragma import check_pragma
from jtc_gov.checks.t import check_t
from jtc_gov.domain.models import CheckResult
from jtc_gov.domain.repo import Repo


def run_all(repo: Repo) -> CheckResult:
    changes = repo.changes()
    findings = [
        *check_k(repo, changes),
        *check_d(repo, changes),
        *check_t(repo, changes),
        *check_pragma(repo, changes),
    ]
    return CheckResult(tuple(findings), human_merge(changes))
