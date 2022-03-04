import os
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

import wandb
import wandb.data_types as data_types
from wandb.data_types import SavedModel
from wandb.sdk.interface.artifacts import (
    Artifact as ArtifactInterface,
    ArtifactEntry,
)


def _add_any(
    artifact: ArtifactInterface,
    path_or_obj: Union[str, ArtifactEntry, data_types.WBValue],  # todo: add dataframe
    name: Optional[str]
    # is_tmp: Optional[bool] = False,
    # checksum: bool = True,
    # max_objects: Optional[int] = None,
):
    if isinstance(path_or_obj, ArtifactEntry):
        return artifact.add_reference(path_or_obj, name)
    elif isinstance(path_or_obj, data_types.WBValue):
        return artifact.add(path_or_obj, name)
    elif isinstance(path_or_obj, str):
        if os.path.isdir(path_or_obj):
            return artifact.add_dir(path_or_obj)
        elif os.path.isfile(path_or_obj):
            return artifact.add_file(path_or_obj)
        else:
            import json

            with artifact.new_file(name) as f:
                f.write(json.dumps(path_or_obj, sort_keys=True))
    else:
        raise ValueError(
            f"Expected `path_or_obj` to be instance of `ArtifactEntry`, `WBValue`, or `str, found {type(path_or_obj)}"
        )


def _log_artifact_version(
    name: str,
    type: str,
    entries: Dict[str, Union[str, ArtifactEntry, data_types.WBValue]],
    aliases: Optional[Union[str, List[str]]] = None,
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    project: Optional[str] = None,
    project_scope: Optional[bool] = None,
    job_type: str = "auto",
) -> ArtifactInterface:
    if wandb.run is None:
        run = wandb.init(
            project=project, job_type=job_type, settings=wandb.Settings(silent="true")
        )
    else:
        run = wandb.run

    if not project_scope:
        name = f"{name}-{run.id}"

    if metadata is None:
        metadata = {}

    # hack for demo purposes
    # if getattr(run, "history", None):
    #     metadata.update({"__wb_log_step__": wandb.run.history._step})

    art = wandb.Artifact(name, type, description, metadata, False, None)

    for path in entries:
        _add_any(art, entries[path], path)

    # "latest" should always be present as an alias in every new logged artifact version.
    if aliases is None:
        aliases = []
    elif isinstance(aliases, str):
        aliases = [aliases]

    if "latest" not in aliases:
        aliases.append("latest")

    run.log_artifact(art, aliases=aliases)

    return art


def log_model(
    model_obj: Any,
    name: str = "model",
    aliases: Optional[Union[str, List[str]]] = None,
    description: Optional[str] = None,
    metadata: Optional[dict] = None,
    project: Optional[str] = None,
) -> "SavedModel":
    model = data_types.SavedModel(model_obj)
    _ = _log_artifact_version(
        name=name,
        type="model",
        entries={"index": model,},
        aliases=aliases,
        description=description,
        metadata=metadata,
        project=project,
        project_scope=False,
        job_type="log_model",
    )

    # TODO: handle offline mode appropriately.
    return model


def use_model(model_alias: str) -> "SavedModel":
    # Returns a SavedModel instance
    if wandb.run:
        run = wandb.run
        artifact = run.use_artifact(model_alias)
        sm = artifact.get("index")
        return sm
    else:
        raise ValueError(
            "use_model can only be called inside a run. Please call wandb.init() before use_model(...)"
        )


def link_model(
    model: "SavedModel",
    registry_path: str,
    aliases: Optional[Union[str, List[str]]] = None,
):
    """
    `registry_path`: str that can take the following form:
        "{portfolio}"
        "{entity}/{project}/{portfolio}"
        "{project}/{portfolio}
    """

    if aliases is None:
        aliases = ["latest"]

    if wandb.run:
        run = wandb.run

        # If the SavedModel has been added to a Local Artifact (most likely through `.add(WBValue)`), then
        # model._artifact_target will point to that Local Artifact.
        if model._artifact_target is not None:
            artifact = model._artifact_target.artifact
        # _artifact_source, if it exists, points to a Public Artifact.
        # Its existence means that SavedModel was deserialized from a logged artifact, most likely from `use_model`.
        elif model._artifact_source is not None:
            artifact = model._artifact_source.artifact
        else:
            raise ValueError(
                "Linking requires that the given SavedModel belongs to an artifact"
            )

        run.link_artifact(artifact, registry_path, aliases)

    else:
        if model._artifact_source is not None:
            model._artifact_source.artifact.link(registry_path, aliases)
        else:
            raise ValueError(
                "Linking requires that the given SavedModel belongs to an artifact"
            )

    # TODO: Will delete the below code/comments.

    # Use Case: a user trains a model, calling log_model several times
    # in a row and saves a reference to the best model every time.
    # At the end, they want to link this model into a portfolio.

    # Use Case: a user wants to evaluate a batch of models and
    # link the best one into a portfolio.

    # Use Case: a user wants to evaluate the latest models in a portfolio
    # and choose the best one to link into the next stage (next portfolio).

    # Automated retraining: a user wants to fire off a training run on new data
    # with the same model architecture. They then want to link this model
    # into one portfolio to compare against the production model.