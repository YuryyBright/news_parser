# infrastructure/task_queue/registry.py
"""
Єдине місце реєстрації задач — імпортується тільки в bootstrap.
Ні application, ні infrastructure/workers не знають один про одного.
"""
from infrastructure.task_queue.background_queue import register_task


def register_all_tasks() -> None:
    register_task(
        "fetch_source",
        "infrastructure.workers.handlers:handle_fetch_source",
    )
    register_task(
        "process_article",
        "infrastructure.workers.handlers:handle_process_article",
    )
    register_task(
        "generate_criteria",
        "infrastructure.workers.handlers:handle_generate_criteria",
    )