"""NOZE Agency — an automated short-form clipping studio run by a team of agents.

Org chart (one deterministic pipeline, five roles):

    Manager ──► finds open clipping campaigns, writes the brief, assigns work,
       │        watches deadlines/budget, gives final approval, delivers, reports
       ▼
    Scout ──► Analyst ──► Editor ──► Reviewer ──► Manager
    (refs)    (blueprint,   (edit plan   (QC + creative   (approve /
               moments)      + render)    review, loops     changes /
                                          back to Editor)   reject)

The flow itself is code (``pipeline.py``); what the team *knows* lives in
playbooks that grow after every job (``learning.py``) behind counters, canary
trials and an automatic rollback, so learning never breaks the flow.
"""
