# -*- coding: utf-8 -*-

"""
Tests that don't hit the Google Music servers.
"""

from collections import namedtuple
import time

from mock import MagicMock as Mock
from proboscis.asserts import (
    assert_raises, assert_true, assert_false, assert_equal,
    assert_is_not, Check
)
from proboscis import test

import gmusicapi.session
from gmusicapi.clients import Webclient, Musicmanager
from gmusicapi.exceptions import AlreadyLoggedIn  # ,NotLoggedIn
from gmusicapi.protocol.shared import authtypes
from gmusicapi.protocol import mobileclient
from gmusicapi.utils import utils


#TODO test gather_local, transcoding

#All tests end up in the local group.
test = test(groups=['local'])

##
# clients
##
# this feels like a dumb pattern, but I can't think of a better way
names = ('Webclient', 'Musicmanager')
Clients = namedtuple('Clients', [n.lower() for n in names])


def create_clients():
    clients = []
    for name in names:
        cls = getattr(gmusicapi.clients, name)
        c = cls()

        # mock out the underlying session
        c.session = Mock()
        clients.append(c)

    return Clients(*clients)


@test
def no_client_auth_initially():
    wc = Webclient()
    assert_false(wc.is_authenticated())

    mm = Musicmanager()
    assert_false(mm.is_authenticated())


@test
def mm_prevents_bad_mac_format():
    mm = create_clients().musicmanager

    with Check() as check:
        for bad_mac in ['bogus',
                        '11:22:33:44:55:66:',
                        '11:22:33:44:55:ab',
                        '11:22:33:44:55']:
            check.raises(
                ValueError,
                mm._perform_upauth,
                uploader_id=bad_mac,
                uploader_name='valid')


# @test
# def auto_playlists_are_empty():
#     # this doesn't actually hit the server at the moment.
#     # see issue 102
#     api = Api()
#     assert_equal(api.get_all_playlist_ids(auto=True, user=False),
#                  {'auto': {}})

##
# sessions
##
Sessions = namedtuple('Sessions', [n.lower() for n in names])


def create_sessions():
    sessions = []
    for name in names:
        cls = getattr(gmusicapi.session, name)
        s = cls()

        # mock out the underlying requests.session
        s._rsession = Mock()
        sessions.append(s)

    return Sessions(*sessions)


@test
def no_session_auth_initially():
    for s in create_sessions():
        assert_false(s.is_authenticated)


@test
def session_raises_alreadyloggedin():
    for s in create_sessions():
        s.is_authenticated = True

        def login():
            # hackish: login ignores args so we can test them all here;
            # this just ensures we have an acceptable amount of args
            s.login(*([None] * 3))

        assert_raises(AlreadyLoggedIn, login)


@test
def session_logout():
    for s in create_sessions():
        s.is_authenticated = True
        old_session = s._rsession
        s.logout()

        assert_false(s.is_authenticated)
        old_session.close.assert_called_once_with()
        assert_is_not(s._rsession, old_session)


@test
def send_without_auth():
    for s in create_sessions():
        s.is_authenticated = True

        mock_session = Mock()
        mock_req_kwargs = {'fake': 'kwargs'}

        s.send(mock_req_kwargs, authtypes(), mock_session)

        # sending without auth should not use the normal session,
        # since that might have auth cookies automatically attached
        assert_false(s._rsession.called)

        mock_session.request.called_once_with(**mock_req_kwargs)
        mock_session.closed.called_once_with()


##
# protocol
##

@test
def authtypes_factory_defaults():
    auth = authtypes()
    assert_false(auth.oauth)
    assert_false(auth.sso)
    assert_false(auth.xt)


@test
def authtypes_factory_args():
    auth = authtypes(oauth=True)
    assert_true(auth.oauth)
    assert_false(auth.sso)
    assert_false(auth.xt)


@test
def mc_url_signing():
    sig, _ = mobileclient.GetStreamUrl.get_signature("Tdr6kq3xznv5kdsphyojox6dtoq",
                                                     "1373247112519")
    assert_equal(sig, "gua1gInBdaVo7_dSwF9y0kodua0")


##
# utils
##

@test
def retry_failure_propogation():
    @utils.retry(tries=1)
    def raise_exception():
        raise AssertionError

    assert_raises(AssertionError, raise_exception)


@test
def retry_sleep_timing():

    @utils.retry(tries=3, delay=.05, backoff=2)
    def raise_exception():
        raise AssertionError

    pre = time.time()
    assert_raises(AssertionError, raise_exception)
    post = time.time()

    delta = post - pre
    assert_true(.15 < delta < .2, "delta: %s" % delta)


@test
def retry_is_dual_decorator():
    @utils.retry
    def return_arg(arg=None):
        return arg

    assert_equal(return_arg(1), 1)
