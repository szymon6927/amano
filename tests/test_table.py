from dataclasses import dataclass
from typing import Iterable

import pytest
from mypy_boto3_dynamodb import DynamoDBClient

from amano import Attribute, Index, Item, Table
from amano.errors import AmanoDBError, ItemNotFoundError, QueryError
from amano.item import _ItemState


def test_can_instantiate(readonly_dynamodb_client, readonly_table) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str

    # when
    my_table = Table[Track](readonly_dynamodb_client, table_name=readonly_table)

    # then
    assert isinstance(my_table, Table)
    assert my_table._item_class == Track


def test_fail_instantiation_on_non_parametrized_table(
    readonly_dynamodb_client, readonly_table
) -> None:
    # when
    with pytest.raises(
        TypeError, match=".* must be parametrized with a subtype of .*"
    ):
        Table(readonly_dynamodb_client, table_name=readonly_table)


def test_fail_instantiation_on_unknown_table(
    readonly_dynamodb_client,
) -> None:
    # given
    class TestItem(Item):
        pk: str
        sk: str

    # when
    with pytest.raises(ValueError):
        Table[TestItem](readonly_dynamodb_client, table_name="TestItem")


def test_can_retrieve_partition_key(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str

    # when
    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # then
    assert my_table.partition_key == "artist_name"


def test_can_retrieve_sort_key(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str

    # when
    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # then
    assert my_table.sort_key == "track_name"


def test_fails_when_item_has_no_pk_defined(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        _artist_name: str
        track_name: str

    # then
    with pytest.raises(AttributeError):
        Table[Track](readonly_dynamodb_client, readonly_table)


def test_fails_when_item_has_no_sk_defined(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        artist_name: str
        _track_name: str

    # then
    with pytest.raises(AttributeError):
        Table[Track](readonly_dynamodb_client, readonly_table)


def test_can_retrieve_indexes(readonly_dynamodb_client, readonly_table) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str

    # when
    table = Table[Track](readonly_dynamodb_client, readonly_table)

    # then
    assert len(table.indexes) == 4
    assert list(table.indexes.keys()) == [
        "#",
        "GlobalGenreAndAlbumNameIndex",
        "GlobalAlbumAndTrackNameIndex",
        "LocalArtistAndAlbumNameIndex",
    ]
    assert all(isinstance(index, Index) for index in table.indexes.values())


def test_can_retrieve_available_indexes(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str

    # when
    table = Table[Track](readonly_dynamodb_client, readonly_table)
    available_indexes = table.available_indexes

    # then
    assert len(available_indexes) == 3
    assert Table._PRIMARY_KEY_NAME in available_indexes
    assert "GlobalAlbumAndTrackNameIndex" in available_indexes
    assert "LocalArtistAndAlbumNameIndex" in available_indexes


def test_can_query_item_by_pk_and_sk(
    readonly_dynamodb_client, readonly_table
) -> None:

    # given
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    item = my_table.get("AC/DC", "Let There Be Rock")

    # then
    assert isinstance(item, Track)
    assert item.artist_name == "AC/DC"
    assert item.track_name == "Let There Be Rock"
    assert item.album_name == "Let There Be Rock"


def test_fail_query_item_by_pk_only(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    with pytest.raises(AmanoDBError) as e:
        item = my_table.get("AC/DC")

    # then
    assert isinstance(e.value, QueryError)


def test_fail_get_unexisting_item(
    readonly_dynamodb_client, readonly_table
) -> None:

    # given
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    with pytest.raises(AmanoDBError) as e:
        item = my_table.get("AC/DC", "Let There Be No Rock")

    # then
    assert isinstance(e.value, ItemNotFoundError)
    assert e.value.query == {
        "artist_name": "AC/DC",
        "track_name": "Let There Be No Rock",
    }


def test_can_put_item(default_dynamodb_client, default_table) -> None:
    # given
    @dataclass
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str

    my_table = Table[Track](default_dynamodb_client, default_table)

    # when
    item = Track("Tool", "Reflection", "Lateralus")
    result = my_table.put(item)

    # then
    assert result


def test_can_put_item_with_condition(
    default_dynamodb_client, default_table
) -> None:

    # given
    @dataclass
    class Track(Item):
        artist_name: Attribute[str]
        track_name: Attribute[str]
        album_name: Attribute[str]

    my_table = Table[Track](default_dynamodb_client, default_table)

    # when
    item = Track("Tool", "Reflection", "Lateralus")
    result = my_table.put(item, condition=Track.artist_name.not_exists())

    # then
    assert result


def test_query_table_with_pk_only(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    @dataclass
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str
        genre_name: str

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    result = my_table.query(Track.album_name == "Let There Be Rock")

    # then
    assert isinstance(result, Iterable)

    all_items = []
    for item in result:
        all_items.append(item)
        assert isinstance(item, Track)

    assert len(all_items) == 8


def test_query_table_with_pk_and_sk(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    @dataclass
    class Track(Item):
        artist_name: str
        track_name: str
        album_name: str
        genre_name: str

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    result = my_table.query(
        (Track.artist_name == "AC/DC") & Track.track_name.startswith("S")
    )

    # then
    assert isinstance(result, Iterable)

    all_items = []
    for item in result:
        all_items.append(item)
        assert isinstance(item, Track)

    assert len(all_items) == 2


def test_query_table_with_pk_and_filter(
    readonly_dynamodb_client, readonly_table
) -> None:
    # given
    @dataclass
    class Track(Item):
        artist_name: Attribute[str]
        track_name: Attribute[str]
        album_name: Attribute[str]
        genre_name: Attribute[str]

    my_table = Table[Track](readonly_dynamodb_client, readonly_table)

    # when
    result = my_table.query(
        key_condition=(Track.artist_name == "AC/DC"),
        filter_condition=Track.genre_name.startswith("R"),
    )

    # then
    assert isinstance(result, Iterable)

    all_items = []
    for item in result:
        all_items.append(item)
        assert isinstance(item, Track)

    assert len(all_items) == 18


def test_can_update_item(default_dynamodb_client, default_table) -> None:
    # given
    class Track(Item):
        artist_name: Attribute[str]
        track_name: Attribute[str]
        album_name: Attribute[str]
        genre_name: Attribute[str]

    tracks = Table[Track](default_dynamodb_client, default_table)

    tracks.put(Track("AC/DC", "Let There Be Rock", "Let There Be Rock", "Rock"))

    track = tracks.get("AC/DC", "Let There Be Rock")
    assert isinstance(track, Track)

    # when
    track.album_name = "Undefined Album"
    tracks.update(track)

    # then
    assert track._state() == _ItemState.CLEAN

    track = tracks.get("AC/DC", "Let There Be Rock")
    assert isinstance(track, Track)
    assert track.album_name == "Undefined Album"


def test_ignore_update_for_non_modified_item(
    default_dynamodb_client, default_table
) -> None:
    # given
    class Track(Item):
        artist_name: Attribute[str]
        track_name: Attribute[str]
        album_name: Attribute[str]
        genre_name: Attribute[str]

    tracks = Table[Track](default_dynamodb_client, default_table)

    track = Track("Artist", "Track", "Album", "Genre")
    tracks.put(track)
    assert track._state() == _ItemState.CLEAN

    # when
    assert not tracks.update(track)

    # then
    assert track._state() == _ItemState.CLEAN
