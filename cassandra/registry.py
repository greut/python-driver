# Copyright DataStax, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from collections import defaultdict

from cassandra import ProtocolVersion
from cassandra.protocol import *


class ProtocolVersionRegistry(object):
    """Default implementation of the ProtocolVersionRegistry"""

    _protocol_versions = None
    """A list of registered protocol versions"""

    _beta_protocol_versions = None
    """A list of registered beta protocol versions"""

    _supported_versions = None

    def __init__(self, protocol_versions, beta_versions=None):
        self._protocol_versions = tuple(protocol_versions)
        self._beta_protocol_versions = tuple(beta_versions or [])
        self._supported_versions = sorted(self._protocol_versions, reverse=True)

    def supported_versions(self):
        """
        Return a tuple of all supported protocol versions.
        """
        return self._supported_versions

    def beta_versions(self):
        """
        Return a tuple of all beta protocol versions.
        """
        return self._beta_protocol_versions

    def min_supported(self):
        """
        Return the minimum protocol version supported by this driver.
        """
        return min(self.supported_versions())

    def max_supported(self):
        """
        Return the maximum protocol version supported by this driver.
        """
        return max(self.supported_versions())

    def get_lower_supported(self, previous_version):
        """
        Return the lower supported protocol version. Beta versions are omitted.
        """
        try:
            version = next(v for v in sorted(self.supported_versions(), reverse=True) if
                           not v.is_beta and v < previous_version)
        except StopIteration:
            version = None

        return version

    def max_non_beta_supported(self):
        return max(v for v in self.supported_versions() if v not in self.beta_versions())

    @classmethod
    def factory(cls, protocol_versions=ProtocolVersion.VERSIONS,
                beta_versions=ProtocolVersion.BETA_VERSIONS):
        """"Factory to construct the default protocol version registry

        :param protocol_versions: The object that is defining all available versions.
        """

        return cls(protocol_versions, beta_versions)


class MessageCodecRegistry(object):
    encoders = None
    decoders = None

    def __init__(self):
        self.encoders = defaultdict(dict)
        self.decoders = defaultdict(dict)

    @staticmethod
    def _add(registry, protocol_version, opcode, func):
        registry[protocol_version][opcode] = func

    @staticmethod
    def _get(registry, protocol_version, opcode):
        try:
            return registry[protocol_version][opcode]
        except KeyError:
            raise ValueError(
                "No codec registered for message '{0:02X}' and "
                "protocol version '{1}'".format(opcode, protocol_version))

    def add_encoder(self, protocol_version, opcode, encoder):
        return self._add(self.encoders, protocol_version, opcode, encoder)

    def add_decoder(self, protocol_version, opcode, decoder):
        return self._add(self.decoders, protocol_version, opcode, decoder)

    def get_encoder(self, protocol_version, opcode):
        return self._get(self.encoders, protocol_version, opcode)

    def get_decoder(self, protocol_version, opcode):
        return self._get(self.decoders, protocol_version, opcode)

    @classmethod
    def factory(cls, protocol_version_registry):
        """Factory to construct the default message codec registry"""

        registry = cls()
        for v in protocol_version_registry.supported_versions():
            for message in [
                StartupMessage,
                RegisterMessage,
                BatchMessage,
                QueryMessage,
                ExecuteMessage,
                PrepareMessage,
                OptionsMessage,
                AuthResponseMessage,
            ]:
                registry.add_encoder(v, message.opcode, message.encode)

            error_decoders = [(e.error_code, e.decode) for e in [
                UnavailableErrorMessage,
                ReadTimeoutErrorMessage,
                WriteTimeoutErrorMessage,
                IsBootstrappingErrorMessage,
                OverloadedErrorMessage,
                UnauthorizedErrorMessage,
                ServerError,
                ProtocolException,
                BadCredentials,
                TruncateError,
                ReadFailureMessage,
                FunctionFailureMessage,
                WriteFailureMessage,
                CDCWriteException,
                SyntaxException,
                InvalidRequestException,
                ConfigurationException,
                PreparedQueryNotFound,
                AlreadyExistsException
            ]]

            for codec in [
                ReadyMessage,
                EventMessage.Codec,
                ResultMessage.Codec,
                AuthenticateMessage,
                AuthSuccessMessage,
                AuthChallengeMessage,
                SupportedMessage,
                ErrorMessage.Codec(error_decoders)

            ]:
                registry.add_decoder(v, codec.opcode, codec.decode)

        return registry
