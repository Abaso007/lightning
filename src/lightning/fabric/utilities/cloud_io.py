# Copyright The Lightning AI team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities related to data saving/loading."""
import io
import logging
from pathlib import Path
from typing import Any, Dict, IO, Union

import fsspec
import torch
from fsspec.core import url_to_fs
from fsspec.implementations.local import AbstractFileSystem
from lightning_utilities.core.imports import module_available

from lightning.fabric.utilities.types import _MAP_LOCATION_TYPE, _PATH

log = logging.getLogger(__name__)


def _load(
    path_or_url: Union[IO, _PATH],
    map_location: _MAP_LOCATION_TYPE = None,
) -> Any:
    """Loads a checkpoint.

    Args:
        path_or_url: Path or URL of the checkpoint.
        map_location: a function, ``torch.device``, string or a dict specifying how to remap storage locations.

    """
    if not isinstance(path_or_url, (str, Path)):
        # any sort of BytesIO or similar
        return torch.load(
            path_or_url,
            map_location=map_location,  # type: ignore[arg-type] # upstream annotation is not correct
        )
    if str(path_or_url).startswith("http"):
        return torch.hub.load_state_dict_from_url(
            str(path_or_url),
            map_location=map_location,  # type: ignore[arg-type]
        )
    fs = get_filesystem(path_or_url)
    with fs.open(path_or_url, "rb") as f:
        return torch.load(f, map_location=map_location)  # type: ignore[arg-type]


def get_filesystem(path: _PATH, **kwargs: Any) -> AbstractFileSystem:
    fs, _ = url_to_fs(str(path), **kwargs)
    return fs


def _atomic_save(checkpoint: Dict[str, Any], filepath: Union[str, Path]) -> None:
    """Saves a checkpoint atomically, avoiding the creation of incomplete checkpoints.

    Args:
        checkpoint: The object to save.
            Built to be used with the ``dump_checkpoint`` method, but can deal with anything which ``torch.save``
            accepts.
        filepath: The path to which the checkpoint will be saved.
            This points to the file that the checkpoint will be stored in.

    """
    bytesbuffer = io.BytesIO()
    log.debug(f"Saving checkpoint: {filepath}")
    torch.save(checkpoint, bytesbuffer)
    with fsspec.open(filepath, "wb") as f:
        f.write(bytesbuffer.getvalue())


def _is_object_storage(fs: AbstractFileSystem) -> bool:
    if module_available("adlfs"):
        from adlfs import AzureBlobFileSystem

        if isinstance(fs, AzureBlobFileSystem):
            return True

    if module_available("gcsfs"):
        from gcsfs import GCSFileSystem

        if isinstance(fs, GCSFileSystem):
            return True

    if module_available("s3fs"):
        from s3fs import S3FileSystem

        if isinstance(fs, S3FileSystem):
            return True

    return False


def _is_dir(fs: AbstractFileSystem, path: Union[str, Path], strict: bool = False) -> bool:
    """Check if a path is directory-like.

    This function determines if a given path is considered directory-like, taking into account the behavior
    specific to object storage platforms. For other filesystems, it behaves similarly to the standard `fs.isdir`
    method.

    Args:
        fs: The filesystem to check the path against.
        path: The path or URL to be checked.
        strict: A flag specific to Object Storage platforms. If set to ``False``, any non-existing path is considered
            as a valid directory-like path. In such cases, the directory (and any non-existing parent directories)
            will be created on the fly. Defaults to False.

    """
    if _is_object_storage(fs):
        return fs.isdir(path) if strict else not fs.isfile(path)
    return fs.isdir(path)
