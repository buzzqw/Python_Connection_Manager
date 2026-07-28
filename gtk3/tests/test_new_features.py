"""
Test suite for new PCM features: plugins, TOTP, password tools,
template inheritance, gateway detection, tag filtering, protocol validation.
"""
import pytest
import os

from plugins.plugin_manager import discover_plugins, load_plugins, get_builtin_plugin_dir
from plugins.plugin_base import (
    pcm_has_protocol, pcm_build_command, pcm_get_protocol_plugins,
    pcm_plugin_protocols,
)
import protocols
from protocols import refresh_from_plugins, register_protocol, validate_profiles
from totp_manager import generate_totp, validate_secret, render_uri_to_secret, extract_otp_from_uri
from password_tools import generate_password, generate_passphrase, check_password_strength
from config_manager import _resolve_template_inheritance, get_templates


class TestPlugins:
    """Plugin system tests."""

    def test_builtin_dir_exists(self):
        d = get_builtin_plugin_dir()
        assert os.path.isdir(d)

    def test_discover_plugins(self):
        discovered = discover_plugins()
        assert len(discovered) >= 4
        for pid in ('aws_ssm', 'kubectl_exec', 'docker_container', 'spice_client'):
            assert pid in discovered, f'{pid} not discovered'

    def test_load_plugins(self):
        loaded = load_plugins()
        assert len(loaded) >= 4
        plugin_ids = {p.plugin_id for p in loaded}
        assert 'aws_ssm' in plugin_ids
        assert 'kubectl_exec' in plugin_ids
        assert 'docker_container' in plugin_ids
        assert 'spice_client' in plugin_ids

    def test_protocol_registration(self):
        load_plugins()
        refresh_from_plugins()
        assert pcm_has_protocol('aws_ssm')
        assert pcm_has_protocol('kubectl_exec')
        assert pcm_has_protocol('docker_container')
        assert pcm_has_protocol('spice')
        assert 'aws_ssm' in protocols.PROTOCOLS

    def test_plugin_commands(self):
        load_plugins()
        refresh_from_plugins()

        cmd, mode = pcm_build_command('aws_ssm', {'host': 'i-abc', 'aws_region': 'us-east-1'})
        assert cmd
        assert 'aws' in cmd
        assert mode == 'embedded'

        cmd, mode = pcm_build_command('kubectl_exec', {'host': 'pod', 'k8s_namespace': 'ns'})
        assert cmd and 'kubectl' in cmd
        assert mode == 'embedded'

        cmd, mode = pcm_build_command('docker_container', {'host': 'cont', 'docker_mode': 'exec'})
        assert cmd and 'docker' in cmd
        assert mode == 'embedded'

        cmd, mode = pcm_build_command('spice', {'host': '192.168.1.1', 'port': '5901'})
        assert cmd and 'spice' in cmd
        assert mode == 'external'

    def test_plugin_no_host(self):
        load_plugins()
        refresh_from_plugins()

        for proto_id in ('aws_ssm', 'kubectl_exec', 'docker_container', 'spice'):
            cmd, mode = pcm_build_command(proto_id, {'host': ''})
            assert cmd is None
            assert mode == 'none'

    def test_protocol_register_unregister(self):
        original = list(protocols.PROTOCOLS)
        register_protocol('test_proto', 'Test', color='#ff0000', default_port='9999',
                          fields={'test_field'})
        assert 'test_proto' in protocols.PROTOCOLS
        assert protocols.PROTO_LABEL['test_proto'] == 'Test'
        assert protocols.DEFAULT_PORT['test_proto'] == '9999'

        protocols.unregister_protocol('test_proto')
        assert 'test_proto' not in protocols.PROTOCOLS
        assert list(protocols.PROTOCOLS) == original


class TestTemplateInheritance:
    """Template inheritance tests."""

    def test_basic_inheritance(self):
        profiles = {
            'T': {'protocol': 'ssh', 'port': '22', 'user': 'admin',
                   'jump_host': 'gw', 'is_template': True},
            'S': {'protocol': 'ssh', 'host': 'srv', 'template_name': 'T'},
        }
        resolved = _resolve_template_inheritance(profiles)
        assert resolved['S']['user'] == 'admin'
        assert resolved['S']['jump_host'] == 'gw'
        assert resolved['S']['_inherits_from'] == 'T'

    def test_override_inheritance(self):
        profiles = {
            'T': {'protocol': 'ssh', 'port': '22', 'user': 'ops', 'is_template': True},
            'S': {'protocol': 'ssh', 'host': 'srv2', 'user': 'custom',
                   'template_name': 'T'},
        }
        resolved = _resolve_template_inheritance(profiles)
        assert resolved['S']['user'] == 'custom', 'override should win'

    def test_no_inheritance_without_template(self):
        profiles = {
            'T': {'protocol': 'ssh', 'port': '22', 'is_template': False},
            'S': {'protocol': 'ssh', 'host': 'srv3', 'user': 'me',
                   'template_name': 'T'},
        }
        resolved = _resolve_template_inheritance(profiles)
        assert '_inherits_from' not in resolved['S']

    def test_standalone_unaffected(self):
        profiles = {
            'T': {'protocol': 'ssh', 'port': '22', 'is_template': True},
            'S': {'protocol': 'rdp', 'host': 'desk', 'user': 'me'},
        }
        resolved = _resolve_template_inheritance(profiles)
        assert 'user' in resolved['S']
        assert '_inherits_from' not in resolved['S']

    def test_no_templates(self):
        profiles = {'S1': {'protocol': 'ssh'}, 'S2': {'protocol': 'rdp'}}
        resolved = _resolve_template_inheritance(profiles)
        assert resolved == profiles


class TestTOTP:
    """TOTP manager tests."""

    def test_generate_totp(self):
        code = generate_totp('JBSWY3DPEHPK3PXP')
        assert len(code) == 6
        assert code.isdigit()

    def test_validate_secret_valid(self):
        assert validate_secret('JBSWY3DPEHPK3PXP')
        assert validate_secret('JBSWY3DPEHPK3PXPAAAA')  # 20 chars

    def test_validate_secret_invalid(self):
        assert not validate_secret('')
        assert not validate_secret('short')
        assert not validate_secret('!!!!####')

    def test_uri_extraction(self):
        uri = 'otpauth://totp/Example:user@host?secret=JBSWY3DPEHPK3PXP&issuer=Example'
        assert render_uri_to_secret(uri) == 'JBSWY3DPEHPK3PXP'
        assert extract_otp_from_uri(uri) == 'JBSWY3DPEHPK3PXP'

    def test_plain_secret_passthrough(self):
        assert render_uri_to_secret('JBSWY3DPEHPK3PXP') == 'JBSWY3DPEHPK3PXP'

    def test_invalid_uri(self):
        assert extract_otp_from_uri('not-a-uri') is None
        assert render_uri_to_secret('not-a-uri') == 'not-a-uri'

    def test_totp_consistency(self):
        secret = 'JBSWY3DPEHPK3PXP'
        code1 = generate_totp(secret)
        code2 = generate_totp(secret)
        assert code1 == code2, 'TOTP should be consistent within same period'

    def test_custom_digits(self):
        code = generate_totp('JBSWY3DPEHPK3PXP', digits=8)
        assert len(code) == 8

    def test_custom_algorithm(self):
        code = generate_totp('JBSWY3DPEHPK3PXP', algorithm='sha256')
        assert len(code) == 6
        assert code.isdigit()


class TestPasswordTools:
    """Password generator and strength checker tests."""

    def test_generate_password_length(self):
        for length in (8, 12, 16, 20, 32, 48, 64):
            pwd = generate_password(length)
            assert len(pwd) == length

    def test_generate_password_randomness(self):
        pwd1 = generate_password(32)
        pwd2 = generate_password(32)
        assert pwd1 != pwd2, 'passwords should be random'

    def test_generate_password_charsets(self):
        pwd = generate_password(100, upper=True, lower=True, digits=True, symbols=True)
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)

        pwd2 = generate_password(100, upper=False, lower=True, digits=False, symbols=False)
        assert pwd2.islower()

    def test_generate_passphrase(self):
        pp = generate_passphrase(4)
        parts = pp.split('-')
        assert 4 <= len(parts) <= 5  # 4 words + optional number

        pp2 = generate_passphrase(6, separator='.')
        parts2 = pp2.split('.')
        assert len(parts2) == 6  # 6 words, number appended to last word

    def test_check_strength_empty(self):
        r = check_password_strength('')
        assert r['score'] == 0
        assert r['label'] == 'Vuota'

    def test_check_strength_weak(self):
        r = check_password_strength('abc')
        assert r['score'] == 0

    def test_check_strength_strong(self):
        # 20 chars, all 4 charsets
        r = check_password_strength('Str0ng!P@ssw0rd-2024')
        assert r['score'] >= 3
        assert r['entropy_bits'] > 80

    def test_check_strength_issues(self):
        r = check_password_strength('short')
        assert len(r['issues']) > 0


class TestTagFiltering:
    """Tag filtering logic tests."""

    def _match_tags(self, dati, tag_filter):
        if not tag_filter:
            return True
        tags_raw = dati.get('tags', '')
        if isinstance(tags_raw, str):
            tags = {t.strip() for t in tags_raw.split(',') if t.strip()}
        elif isinstance(tags_raw, list):
            tags = {str(t).strip() for t in tags_raw if str(t).strip()}
        else:
            return False
        return tag_filter in tags

    def test_basic(self):
        assert self._match_tags({'tags': 'prod,database'}, 'prod')
        assert self._match_tags({'tags': 'prod,database'}, 'database')

    def test_no_match(self):
        assert not self._match_tags({'tags': 'prod,database'}, 'staging')

    def test_empty_tag(self):
        assert self._match_tags({'tags': ''}, '')
        assert not self._match_tags({'tags': ''}, 'prod')

    def test_empty_filter(self):
        assert self._match_tags({'tags': 'anything'}, '')

    def test_list_format(self):
        assert self._match_tags({'tags': ['prod', 'staging']}, 'prod')
        assert not self._match_tags({'tags': ['prod']}, 'staging')


class TestGatewayDetection:
    """SSH gateway detection logic tests."""

    def _needs_gateway(self, dati):
        proto = dati.get('protocol', '')
        jump_host = dati.get('jump_host', '').strip()
        return bool(jump_host and proto not in ('ssh', 'mosh', 'serial', 'telnet', 'exec'))

    def test_rdp_needs_gateway(self):
        assert self._needs_gateway({'protocol': 'rdp', 'jump_host': 'gw'})

    def test_vnc_needs_gateway(self):
        assert self._needs_gateway({'protocol': 'vnc', 'jump_host': 'gw'})

    def test_ssh_no_gateway(self):
        assert not self._needs_gateway({'protocol': 'ssh', 'jump_host': 'gw'})
        assert not self._needs_gateway({'protocol': 'mosh', 'jump_host': 'gw'})

    def test_no_jump_host(self):
        assert not self._needs_gateway({'protocol': 'rdp', 'jump_host': ''})
        assert not self._needs_gateway({'protocol': 'rdp'})

    def test_plugin_proto_needs_gateway(self):
        assert self._needs_gateway({'protocol': 'aws_ssm', 'jump_host': 'gw'})


class TestProtocolValidation:
    """Protocol validation tests for new fields."""

    def test_new_fields_preserved(self):
        profiles = {
            's1': {
                'protocol': 'ssh', 'host': 'example.com',
                'totp_secret': 'JBSWY3DPEHPK3PXP',
                'tags': 'prod,web',
                'is_template': False,
                'template_name': '',
                'jump_host': 'bastion',
                'jump_user': 'admin',
                'jump_port': '22',
            }
        }
        validated = validate_profiles(profiles)
        assert 's1' in validated
        v = validated['s1']
        assert v['totp_secret'] == 'JBSWY3DPEHPK3PXP'
        assert v['tags'] == 'prod,web'
        assert v['is_template'] is False
        assert v['template_name'] == ''
        assert v['jump_host'] == 'bastion'

    def test_new_fields_on_rdp(self):
        profiles = {
            'r1': {
                'protocol': 'rdp', 'host': 'win.example.com',
                'totp_secret': 'ABC123',
                'tags': 'staging,rdp',
                'jump_host': 'bastion',
            }
        }
        validated = validate_profiles(profiles)
        assert 'r1' in validated
        v = validated['r1']
        assert v['totp_secret'] == 'ABC123'
        assert v['tags'] == 'staging,rdp'
        assert v['jump_host'] == 'bastion'

    def test_unknown_protocol_excluded(self):
        profiles = {'bad': {'protocol': 'xyz'}}
        validated = validate_profiles(profiles)
        assert 'bad' not in validated

    def test_extra_fields_removed(self):
        profiles = {'s1': {'protocol': 'ssh', 'host': 'h', 'unknown_field': 42}}
        validated = validate_profiles(profiles)
        assert 'unknown_field' not in validated['s1']
