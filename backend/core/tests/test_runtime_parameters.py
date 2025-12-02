from interactem.core.models.runtime import (
    RuntimeOperatorParameter,
    RuntimeOperatorParameterMount,
    RuntimeOperatorParameterString,
    RuntimeParameterCollection,
    RuntimeParameterCollectionType,
)


def test_from_parameter_list_filters_and_builds_cache():
    s = RuntimeOperatorParameterString(
        name="p1",
        label="P1",
        description="a string param",
        type="str",
        default="d",
        required=False,
        value=None,
    )

    m = RuntimeOperatorParameterMount(
        name="m1",
        label="M1",
        description="a mount param",
        type="mount",
        default="/foo",
        required=False,
        value=None,
    )

    # Wrap them as runtime parameter RootModels
    wrapped_s = RuntimeOperatorParameter.model_validate(s)
    wrapped_m = RuntimeOperatorParameter.model_validate(m)

    # OPERATOR collection should only include string param
    coll = RuntimeParameterCollection.from_parameter_list(
        [wrapped_s, wrapped_m], RuntimeParameterCollectionType.OPERATOR
    )
    assert "p1" in coll.parameters
    assert "m1" not in coll.parameters

    # MOUNT collection should only include mount param
    coll2 = RuntimeParameterCollection.from_parameter_list(
        [wrapped_s, wrapped_m], RuntimeParameterCollectionType.MOUNT
    )
    assert "m1" in coll2.parameters
    assert "p1" not in coll2.parameters


def test_update_value_changes_cache_and_returns_flag():
    s = RuntimeOperatorParameterString(
        name="p1",
        label="P1",
        description="a string param",
        type="str",
        default="d",
        required=False,
        value=None,
    )

    wrapped = RuntimeOperatorParameter(root=s)
    coll = RuntimeParameterCollection(type=RuntimeParameterCollectionType.OPERATOR, parameters={"p1": wrapped})

    # Update value -> should return True and cache should reflect
    changed = coll.update_value("p1", "new")
    assert changed is True
    assert coll.values["p1"] == "new"

    # Updating to same value -> False
    changed2 = coll.update_value("p1", "new")
    assert changed2 is False
