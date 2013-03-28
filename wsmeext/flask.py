from __future__ import absolute_import

import functools
import logging
import sys

import wsme
import wsme.api
import wsme.rest.json
import wsme.rest.xml
import wsme.rest.args

import flask

log = logging.getLogger(__name__)


TYPES = {
    'application/json': wsme.rest.json,
    'application/xml': wsme.rest.xml,
    'text/xml': wsme.rest.xml
}


def get_dataformat():
    if 'Accept' in flask.request.headers:
        for t in TYPES:
            if t in flask.request.headers['Accept']:
                return TYPES[t]

    # Look for the wanted data format in the request.
    req_dataformat = getattr(flask.request, 'response_type', None)
    if req_dataformat in TYPES:
        return TYPES[req_dataformat]

    log.info('''Could not determine what format is wanted by the
             caller, falling back to json''')
    return wsme.rest.json


def signature(*args, **kw):
    sig = wsme.signature(*args, **kw)

    def decorator(f):
        sig(f)
        funcdef = wsme.api.FunctionDefinition.get(f)
        funcdef.resolve_types(wsme.types.registry)

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            args, kwargs = wsme.rest.args.get_args(
                funcdef, args, kwargs,
                flask.request.args, flask.request.form,
                flask.request.data,
                flask.request.mimetype
            )

            dataformat = get_dataformat()

            try:
                result = f(*args, **kwargs)

                # NOTE: Support setting of status_code with default 200
                status_code = 200
                if isinstance(result, wsme.api.Response):
                    result = result.result
                    status_code = result.status_code

                if funcdef.status_code:
                    status_code = funcdef.status_code

                res = flask.make_response(
                    dataformat.encode_result(
                        result,
                        funcdef.return_type
                    )
                )
                res.mimetype = dataformat.content_type
                res.status_code = status_code
            except:
                data = wsme.api.format_exception(sys.exc_info())
                res = flask.make_response(dataformat.encode_error(None, data))
                if data['faultcode'] == 'client':
                    res.status_code = 400
                else:
                    res.status_code = 500
            return res

        wrapper.wsme_func = f
        return wrapper
    return decorator