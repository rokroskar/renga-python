# -*- coding: utf-8 -*-
#
# Copyright 2017-2018 - Swiss Data Science Center (SDSC)
# A partnership between École Polytechnique Fédérale de Lausanne (EPFL) and
# Eidgenössische Technische Hochschule Zürich (ETHZ).
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
"""Model objects representing datasets."""

import datetime
import re
import uuid
from functools import partial

import attr
from attr.validators import instance_of
from dateutil.parser import parse as parse_date

from renga._compat import Path

from . import _jsonld as jsonld

NoneType = type(None)

_path_attr = partial(
    jsonld.ib,
    converter=Path,
    validator=lambda i, arg, val: Path(val).absolute().is_file()
)


def _deserialize_set(s, cls):
    """Deserialize a list of dicts into classes."""
    return set(
        cls.from_jsonld(x) if hasattr(cls, 'from_jsonld') else cls(**x)
        for x in s
    )


def _deserialize_dict(d, cls):
    """Deserialize a list of dicts into classes."""
    return {
        k: cls.from_jsonld(v) if hasattr(cls, 'from_jsonld') else cls(**v)
        for k, v in d.items()
    }


@jsonld.s(
    type='dcterms:creator',
    context={
        'foaf': 'http://xmlns.com/foaf/0.1/',
        'dcterms': 'http://purl.org/dc/terms/',
        'scoro': 'http://purl.org/spar/scoro/',
    },
    frozen=True,
)
class Author(object):
    """Represent the author of a resource."""

    name = jsonld.ib(validator=instance_of(str), context='dcterms:name')
    email = jsonld.ib(context='dcterms:email')
    affiliation = jsonld.ib(default=None, context='scoro:affiliate')

    @email.validator
    def check_email(self, attribute, value):
        """Check that the email is valid."""
        if not (
            isinstance(value, str) and re.match(r"[^@]+@[^@]+\.[^@]+", value)
        ):
            raise ValueError('Email address is invalid.')

    @classmethod
    def from_git(cls, git):
        """Create an instance from a Git repo."""
        git_config = git.config_reader()
        return cls(
            name=git_config.get('user', 'name'),
            email=git_config.get('user', 'email'),
        )


def _deserialize_authors(authors):
    """Deserialize authors in various forms."""
    if isinstance(authors, dict):
        return set([Author(**authors)])
    elif isinstance(authors, Author):
        return set([authors])
    elif isinstance(authors, (set, list)):
        if all(isinstance(x, dict) for x in authors):
            return _deserialize_set(authors, Author)
        elif all(isinstance(x, Author) for x in authors):
            return authors

    raise ValueError(
        'Authors must be a dict or '
        'set or list of dicts or Author.'
    )


@jsonld.s
class DatasetFile(object):
    """Represent a file in a dataset."""

    path = _path_attr()
    origin = attr.ib(converter=lambda x: str(x))
    authors = jsonld.ib(
        default=attr.Factory(set),
        converter=_deserialize_authors,
    )
    dataset = attr.ib(default=None)
    added = jsonld.ib(context='http://schema.org/dateCreated', )

    @added.default
    def _now(self):
        """Define default value for datetime fields."""
        return datetime.datetime.utcnow()


_deserialize_files = partial(_deserialize_dict, cls=DatasetFile)


def _parse_date(value):
    """Convert date to datetime."""
    if isinstance(value, datetime.datetime):
        return value
    return parse_date(value)


@jsonld.s(
    type='dctypes:Dataset',
    context={
        'dcterms': 'http://purl.org/dc/terms/',
        'dctypes': 'http://purl.org/dc/dcmitypes/',
        'foaf': 'http://xmlns.com/foaf/0.1/',
        'prov': 'http://www.w3.org/ns/prov#',
        'scoro': 'http://purl.org/spar/scoro/',
    },
)
class Dataset(object):
    """Repesent a dataset."""

    SUPPORTED_SCHEMES = ('', 'file', 'http', 'https')

    name = jsonld.ib(type='string', context='foaf:name')

    created = jsonld.ib(
        converter=_parse_date,
        context='http://schema.org/dateCreated',
    )

    identifier = jsonld.ib(
        default=attr.Factory(uuid.uuid4),
        converter=lambda x: uuid.UUID(str(x)),
        context={
            '@id': 'dctypes:Dataset',
            '@type': '@id',
        },
    )
    authors = jsonld.ib(
        default=attr.Factory(set),  # FIXME should respect order
        converter=_deserialize_authors,
        context={
            '@id': Author._jsonld_type,
            '@container': '@list',
        },
    )
    files = jsonld.ib(
        default=attr.Factory(dict),
        converter=_deserialize_files,
        context={
            '@id': DatasetFile._jsonld_type,
            '@container': '@index',
        },
    )

    @created.default
    def _now(self):
        """Define default value for datetime fields."""
        return datetime.datetime.utcnow()