from main import Config, load_config_dict


def _write(path, text):
    path.write_text(text, encoding='utf-8')
    return path


def test_layers_searches_then_local_then_env(tmp_path):
    searches = _write(tmp_path / 'searches.yaml', 'pages: 30\nremax_full_url: "r{}"\nargenprop_full_url: "a{}"\n')
    local = _write(tmp_path / 'config.yaml', 'bot_token: "local"\nchat_room: "c"\npages: 5\n')

    data = load_config_dict(local, searches, {'TELEGRAM_BOT_TOKEN': 'env', 'DATABASE_URL': 'postgresql://x'})

    assert data['pages'] == 5                     # config.yaml pisa searches.yaml
    assert data['bot_token'] == 'env'             # el entorno pisa config.yaml
    assert data['database_url'] == 'postgresql://x'
    assert data['remax_full_url'] == 'r{}'        # lo demas sale de searches.yaml
    Config(**data)


def test_works_without_local_config_using_env_only(tmp_path):
    searches = _write(tmp_path / 'searches.yaml', 'remax_full_url: "r{}"\n')
    data = load_config_dict(tmp_path / 'no-existe.yaml', searches,
                            {'TELEGRAM_BOT_TOKEN': 't', 'TELEGRAM_CHAT_ID': '-1'})
    assert Config(**data).chat_room == '-1'


def test_skip_sites(tmp_path):
    searches = _write(tmp_path / 'searches.yaml', 'remax_full_url: "r{}"\nargenprop_full_url: "a{}"\n')
    data = load_config_dict(tmp_path / 'x.yaml', searches, {'SKIP_SITES': 'Argenprop, roomix'})
    assert 'argenprop_full_url' not in data and data['remax_full_url'] == 'r{}'


def test_repo_searches_file_has_no_secrets():
    import yaml
    from main import ROOT
    data = yaml.safe_load((ROOT / 'searches.yaml').read_text(encoding='utf-8'))
    assert not {'bot_token', 'chat_room', 'database_url'} & set(data)
