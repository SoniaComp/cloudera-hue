# Licensed to Cloudera, Inc. under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  Cloudera, Inc. licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from unittest.mock import patch, Mock

from desktop.conf import SDXAAS
from desktop.lib.sdxaas.knox_jwt import handle_knox_ha, fetch_jwt
from desktop.lib.exceptions_renderable import PopupException


def test_handle_knox_ha():
  with patch('desktop.lib.sdxaas.knox_jwt.requests_kerberos.HTTPKerberosAuth') as HTTPKerberosAuth:
    with patch('desktop.lib.sdxaas.knox_jwt.requests.get') as requests_get:

      requests_get.return_value = Mock(status_code=200)

      # Non-HA mode
      reset = SDXAAS.TOKEN_URL.set_for_testing('https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/')
      try:
        knox_url = handle_knox_ha()

        assert knox_url == 'https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/'
        assert requests_get.call_count == 0 # Simply returning the URL string
      finally:
        reset()
        requests_get.reset_mock()

      # HA mode - When gateway0 is healthy and gateway1 is unhealthy
      requests_get.side_effect = [Mock(status_code=200), Mock(status_code=404)]
      reset = SDXAAS.TOKEN_URL.set_for_testing(
        'https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/, https://knox-gateway1.gethue.com:8443/dl-name/kt-kerberos/')

      try:
        knox_url = handle_knox_ha()

        assert knox_url == 'https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/'
        assert requests_get.call_count == 1
      finally:
        reset()
        requests_get.reset_mock()

      # HA mode - When gateway0 is unhealthy and gateway1 is healthy
      requests_get.side_effect = [Mock(status_code=404), Mock(status_code=200)]
      reset = SDXAAS.TOKEN_URL.set_for_testing(
        'https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/, https://knox-gateway1.gethue.com:8443/dl-name/kt-kerberos/')

      try:
        knox_url = handle_knox_ha()

        assert knox_url == 'https://knox-gateway1.gethue.com:8443/dl-name/kt-kerberos/'
        assert requests_get.call_count == 2
      finally:
        reset()
        requests_get.reset_mock()

      # When both gateway0 and gateway1 are unhealthy
      requests_get.return_value = Mock(status_code=404)
      reset = SDXAAS.TOKEN_URL.set_for_testing(
        'https://knox-gateway0.gethue.com:8443/dl-name/kt-kerberos/, https://knox-gateway1.gethue.com:8443/dl-name/kt-kerberos/')

      try:
        knox_url = handle_knox_ha()

        assert knox_url == None
        assert requests_get.call_count == 2
      finally:
        reset()
        requests_get.reset_mock()


def test_fetch_jwt():
  with patch('desktop.lib.sdxaas.knox_jwt.requests_kerberos.HTTPKerberosAuth') as HTTPKerberosAuth:
    with patch('desktop.lib.sdxaas.knox_jwt.requests.get') as requests_get:
      with patch('desktop.lib.sdxaas.knox_jwt.handle_knox_ha') as handle_knox_ha:

        handle_knox_ha.return_value = 'https://knox-gateway.gethue.com:8443/dl-name/kt-kerberos/'
        requests_get.return_value = Mock(text='{"access_token":"test_jwt_token"}')

        jwt_token = fetch_jwt()

        requests_get.assert_called_with(
          'https://knox-gateway.gethue.com:8443/dl-name/kt-kerberos/knoxtoken/api/v1/token?knox.token.include.groups=true', 
          auth=HTTPKerberosAuth(), 
          verify=False
        )
        assert jwt_token == "test_jwt_token"

        # Raises PopupException when knox_url is not available
        handle_knox_ha.return_value = None
        with pytest.raises(PopupException):
          fetch_jwt()
