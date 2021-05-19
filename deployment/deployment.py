import os

from bitcoinlib.wallets import Wallet
import ubiops


class NoPrivateKeyFound(Exception):
    pass


class InvalidPathProvided(Exception):
    pass


class Deployment:

    def __init__(self, *args, **kwargs):

        self.project_name = os.environ.get('PROJECT_NAME')
        self.deployment_name = os.environ.get('DEPLOYMENT_NAME')

        # Initialize bitcoin wallet
        passphrase = os.environ.get('MNEMONIC_PASSPHRASE', None)
        if passphrase is None:
            raise NoPrivateKeyFound
        try:
            self.wallet = Wallet.create("Wallet", keys=passphrase, network='bitcoin', witness_type='segwit')
        except Exception as e:
            raise e

        # Initialize Ubiops Client
        ubiops_api_token = os.environ.get('UBIOPS_API_TOKEN', None)
        # internal_ubiops_api_host = os.environ.get('INT_API_URL')

        ubiops_conf = ubiops.Configuration(
            # host=internal_ubiops_api_host,
            api_key={'Authorization': 'Token {}'.format(ubiops_api_token)},
        )
        client = ubiops.ApiClient(ubiops_conf)
        self.ubiops_api = ubiops.api.CoreApi(client)

        environment_variables = self.ubiops_api.deployment_environment_variables_list(self.project_name, self.deployment_name)

        self.last_used_path_index = os.environ.get('LAST_USED_PATH_INDEX', '0/0')
        self.last_used_path_index_env = None
        for env in environment_variables:
            if env.name == 'LAST_USED_PATH_INDEX':
                self.last_used_path_index_env = env

        print("Wallet initialized successfuly.")

    def _get_next_unused_path(self):
        MAX_INDEX = 1000

        path_tokens = [int(t) for t in self.last_used_path_index.split("/")]
        if len(path_tokens) != 2:
            raise InvalidPathProvided

        path_tokens[1] = min(MAX_INDEX, path_tokens[1] + 1)

        return path_tokens

    def _get_address_for_path(self, path):
        return self.wallet.key_for_path(path).address

    def _get_invoice(self, address, amount):
        return "{}?amount={}".format(address.upper(), amount)

    def _update_last_used_path(self, path):
        new_value = "/".join([str(t) for t in path])
        data = ubiops.EnvironmentVariableCreate(name=self.last_used_path_index_env.name, value=new_value, secret=True)
        self.ubiops_api.deployment_environment_variables_update(self.project_name, self.deployment_name, self.last_used_path_index_env.id, data)
        self.last_used_path_index = new_value

    def request(self, data):
        next_path = self._get_next_unused_path()
    
        new_address = self._get_address_for_path(next_path)
        amount_in_sats = data.get("sats", 1000)
        invoice = self._get_invoice(new_address, amount_in_sats)

        self._update_last_used_path(next_path)

        return {
            "address": new_address,
            "amount": amount_in_sats,
            "invoice": invoice
        }
