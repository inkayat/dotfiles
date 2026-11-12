---
description: Run one named job through the TLW workflow, under normal FirstMate supervision
argument-hint: "<task description>"
---
The user invoked `/tlw` for one named job. The job description follows, as the harness passed it (quoting and line breaks may be normalized). It is empty when the command had no argument.

$ARGUMENTS

If the job description above is empty or blank, ask which job to run and stop. Do not select or start any TLW or project job, pick a next item or start a wave; your normal FirstMate supervision and lifecycle duties are unaffected.

Otherwise treat this as an ordinary FirstMate request, not a special mode. Resolve the project, the authority and the assignment through your normal process, and keep owning intake, delegation and supervision. TLW is only the inner workflow for this one named job: whoever carries it out MUST read and apply the canonical first-party TLW skill before doing anything else. It is `first-party/tlw/SKILL.md` in the `skills` project of the FirstMate project registry, or the installed `tlw` skill when one exists. If you cannot find it, report that and stop; never rebuild it from memory.

This command alone grants no authority: not model calls, GitHub writes, merging, publishing, installing or changing models. The skill's preconditions and the task's own authority decide what is allowed, and a missing prerequisite stops the job.
