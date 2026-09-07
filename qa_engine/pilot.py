from qa_engine.domain import RunRequest


def validate_pilots(engine, project_ids, *, controlled=False):
    """Explicit enrolled IDs only. Never discovers or mutates unrelated repositories."""
    results = []
    for project_id in project_ids:
        engine.store.project(project_id)
        result = engine.run(RunRequest(project_id=project_id))
        results.append({"project_id": project_id, "run_id": result.run_id, "gate": result.gate.decision, "controlled_fixture": controlled})
    return {"runs": results, "external_three_project_proof": "NOT YET EXECUTED" if controlled else "EXECUTED"}
