import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET

from service.arca_ws import ArcaRuntimeConfig, normalize_env, wsaa_get_ta, wsfe_cae_solicitar, wsfe_comp_consultar


class ArcaWsTests(unittest.TestCase):
    def test_normalize_env_aliases(self):
        self.assertEqual(normalize_env('prod'), 'produccion')
        self.assertEqual(normalize_env('homolog'), 'homologacion')
        self.assertEqual(normalize_env('unknown'), 'homologacion')

    @patch('service.arca_ws._wsaa_login_cms')
    @patch('service.arca_ws._sign_tra_cms_b64')
    @patch('service.arca_ws._validate_runtime_config')
    def test_wsaa_get_ta_uses_cache(self, _mock_validate, _mock_sign, mock_login):
        class DummyCache:
            def __init__(self):
                self.store = {}

            def get(self, key):
                return self.store.get(key)

            def set(self, key, value, ttl):
                self.store[key] = value

        dummy_cache = DummyCache()

        mock_login.return_value = (
            {
                'token': 'token-1',
                'sign': 'sign-1',
                'expiration_time': '2030-01-01T00:00:00+00:00',
                'generation_time': '2029-12-31T23:00:00+00:00',
            },
            '<xml/>',
        )
        cfg = ArcaRuntimeConfig(
            env='homologacion',
            cuit='20123456789',
            cert_path='C:/fake/cert.crt',
            key_path='C:/fake/key.key',
        )
        with patch('service.arca_ws.cache', dummy_cache):
            first = wsaa_get_ta(cfg)
            second = wsaa_get_ta(cfg)
        self.assertEqual(first.get('source'), 'fresh')
        self.assertEqual(second.get('source'), 'cache')
        self.assertEqual(mock_login.call_count, 1)

    @patch('service.arca_ws._validate_runtime_config')
    @patch('service.arca_ws._wsfe_call')
    def test_wsfe_cae_solicitar_parse_authorized(self, mock_call, _mock_validate):
        mock_call.return_value = (
            ET.fromstring(
                '''
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <FECAESolicitarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
                      <FECAESolicitarResult>
                        <FeDetResp>
                          <FECAEDetResponse>
                            <Resultado>A</Resultado>
                            <CbteDesde>123</CbteDesde>
                            <CbteHasta>123</CbteHasta>
                            <CAE>12345678901234</CAE>
                            <CAEFchVto>20261231</CAEFchVto>
                          </FECAEDetResponse>
                        </FeDetResp>
                      </FECAESolicitarResult>
                    </FECAESolicitarResponse>
                  </soap:Body>
                </soap:Envelope>
                '''
            ),
            '<xml/>',
        )
        cfg = ArcaRuntimeConfig(
            env='homologacion',
            cuit='20123456789',
            cert_path='C:/fake/cert.crt',
            key_path='C:/fake/key.key',
        )
        out = wsfe_cae_solicitar(
            cfg,
            auth={'token': 't', 'sign': 's', 'cuit': '20123456789'},
            request_data={
                'pto_vta': 1,
                'cbte_tipo': 6,
                'cbte_nro': 123,
                'doc_tipo': 96,
                'doc_nro': 12345678,
                'imp_total': '100.00',
            },
        )
        self.assertEqual(out.get('resultado'), 'A')
        self.assertEqual(out.get('cae'), '12345678901234')
        self.assertEqual(int(out.get('cbte_nro') or 0), 123)

    @patch('service.arca_ws._validate_runtime_config')
    @patch('service.arca_ws._wsfe_call')
    def test_wsfe_comp_consultar_not_found(self, mock_call, _mock_validate):
        mock_call.return_value = (
            ET.fromstring(
                '''
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                  <soap:Body>
                    <FECompConsultarResponse xmlns="http://ar.gov.afip.dif.FEV1/">
                      <FECompConsultarResult>
                        <Errors>
                          <Err>
                            <Code>602</Code>
                            <Msg>No existe comprobante</Msg>
                          </Err>
                        </Errors>
                      </FECompConsultarResult>
                    </FECompConsultarResponse>
                  </soap:Body>
                </soap:Envelope>
                '''
            ),
            '<xml/>',
        )
        cfg = ArcaRuntimeConfig(
            env='homologacion',
            cuit='20123456789',
            cert_path='C:/fake/cert.crt',
            key_path='C:/fake/key.key',
        )
        out = wsfe_comp_consultar(cfg, auth={'token': 't', 'sign': 's', 'cuit': '20123456789'}, pto_vta=1, cbte_tipo=6, cbte_nro=123)
        self.assertFalse(out.get('found'))
        self.assertTrue(out.get('errors'))


if __name__ == '__main__':
    unittest.main()
