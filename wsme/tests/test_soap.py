import decimal
import datetime
import base64

import wsme.tests.protocol

try:
    import xml.etree.ElementTree as et
except:
    import cElementTree as et

import wsme.soap
import wsme.utils

tns = "http://foo.bar.baz/soap/"
typenamespace = "http://foo.bar.baz/types/"

soapenv_ns = 'http://schemas.xmlsoap.org/soap/envelope/'
xsi_ns = 'http://www.w3.org/2001/XMLSchema-instance'
body_qn = '{%s}Body' % soapenv_ns
fault_qn = '{%s}Fault' % soapenv_ns
faultcode_qn = '{%s}faultcode' % soapenv_ns
faultstring_qn = '{%s}faultstring' % soapenv_ns
faultdetail_qn = '{%s}detail' % soapenv_ns
type_qn = '{%s}type' % xsi_ns
nil_qn = '{%s}nil' % xsi_ns

def build_soap_message(method, params=""):
    message = """<?xml version="1.0"?>
<soap:Envelope
xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
soap:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">

  <soap:Body xmlns="%(typenamespace)s">
    <%(method)s>
        %(params)s
    </%(method)s>
  </soap:Body>

</soap:Envelope>
""" % dict(method=method,
            params=params,
            typenamespace=typenamespace)
    return message


python_types = {
    int: ('xsd:int', str),
    float: ('xsd:float', str),
    str: ('xsd:string', str),
    unicode: ('xsd:string', unicode),
    wsme.types.binary: ('xsd:base64Binary', base64.encodestring),
    decimal.Decimal: ('xsd:decimal', str),
    datetime.date: ('xsd:date', datetime.date.isoformat),
    datetime.time: ('xsd:time', datetime.time.isoformat),
    datetime.datetime: ('xsd:dateTime', datetime.datetime.isoformat),
}

def tosoap(tag, value):
    if isinstance(value, tuple):
        value, datatype = value
    else:
        datatype = type(value)
    print datatype
    el = et.Element(tag)
    if value is None:
        el.set('xsi:nil', True)
    elif datatype in python_types:
        stype, conv = python_types[datatype]
        el.text = conv(value)
        el.set('xsi:type', stype)
    else:
        el.set('xsi:type', datatype.__name__)
        for name, attr in datatype._wsme_attributes:
            if name in value:
                el.append(tosoap(name, (value[name], attr.datatype)))
                    
    return el

def read_bool(value):
    return value == 'true'

soap_types = {
    'xsd:string': unicode,
    'xsd:int': int,
    'xsd:long': long,
    'xsd:float': float,
    'xsd:decimal': decimal.Decimal,
    'xsd:boolean': read_bool,
    'xsd:date': wsme.utils.parse_isodate,
    'xsd:time': wsme.utils.parse_isotime,
    'xsd:dateTime': wsme.utils.parse_isodatetime,
    'xsd:base64Binary': base64.decodestring,
}

def fromsoap(el):
    if el.get(nil_qn) == 'true':
        return None
    t = el.get(type_qn)
    print t
    if t in soap_types:
        print t, el.text
        return soap_types[t](el.text)
    else:
        d = {}
        for child in el:
            name = child.tag
            assert name.startswith('{%s}' % typenamespace)
            name = name[len(typenamespace)+2:]
            d[name] = fromsoap(child)
        print d
        return d


class TestSOAP(wsme.tests.protocol.ProtocolTestCase):
    protocol = wsme.soap.SoapProtocol(
        tns=tns, typenamespace=typenamespace)

    def test_simple_call(self):
        message = build_soap_message('Touch')
        print message
        res = self.app.post('/', message,
            headers={
                "Content-Type": "application/soap+xml; charset=utf-8"
        }, expect_errors=True)
        print res.body
        assert res.status.startswith('200')

    def call(self, fpath, _rt=None, **kw):
        path = fpath.strip('/').split('/')
        # get the actual definition so we can build the adequate request
        if kw:
            el = et.Element('parameters')
            for key, value in kw.items():
                el.append(tosoap(key, value))
            
            params = et.tostring(el)
        else:
            params = ""
        methodname = ''.join((i.capitalize() for i in path))
        message = build_soap_message(methodname, params)
        print message
        res = self.app.post('/', message,
            headers={
                "Content-Type": "application/soap+xml; charset=utf-8"
        }, expect_errors=True)
        print "Status: ", res.status, "Received:", res.body

        el = et.fromstring(res.body)
        body = el.find(body_qn)
        print body
        
        if res.status_int == 200:
            r = body.find('{%s}%sResponse' % (typenamespace, methodname))
            result = r.find('{%s}result' % typenamespace)
            print "Result element: ", result
            return fromsoap(result)
        elif res.status_int == 400:
            fault = body.find(fault_qn)
            raise wsme.tests.protocol.CallException(
                    fault.find(faultcode_qn).text,
                    fault.find(faultstring_qn).text,
                    "")
            
        elif res.status_int == 500:
            fault = body.find(fault_qn)
            raise wsme.tests.protocol.CallException(
                    fault.find(faultcode_qn).text,
                    fault.find(faultstring_qn).text,
                    fault.find(faultdetail_qn).text)
        

        if el.tag == 'error':
            raise wsme.tests.protocol.CallException(
                    el.find('faultcode').text,
                    el.find('faultstring').text,
                    el.find('debuginfo') is not None and
                        el.find('debuginfo').text or None)

        else:
            return loadxml(et.fromstring(res.body))

    def test_wsdl(self):
        res = self.app.get('/api.wsdl')
        print res.body
        assert 'ReturntypesGetunicode' in res.body