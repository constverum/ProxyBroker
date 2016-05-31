
API Reference
=============


.. _proxybroker-api-broker:

Broker
------

.. autoclass:: proxybroker.api.Broker
    :members: grab, find, serve, stop, show_stats


.. _proxybroker-api-proxy:

Proxy
-----

.. autoclass:: proxybroker.proxy.Proxy
    :members: create, types, is_working, avg_resp_time, geo, error_rate, get_log
    :member-order: groupwise


.. _proxybroker-api-provider:

Provider
--------

.. autoclass:: proxybroker.providers.Provider
    :members: proxies, get_proxies
    :member-order: groupwise
