from dagster import AutomationCondition

PIPELINE_CONDITION = (
    AutomationCondition.eager()
    & AutomationCondition.any_deps_match(
        AutomationCondition.any_new_update_has_run_tags(tag_values={"CASCADE": "true"})
    ).since_last_handled()
)
