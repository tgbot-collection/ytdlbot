#!/usr/bin/env python3
# coding: utf-8

# ytdlbot - transfer.py
# 2023-12-07  18:21
from tronpy import Tron
from tronpy.hdwallet import seed_from_mnemonic, key_from_seed
from tronpy.keys import PrivateKey

mnemonic = "web horse smile ramp olive slush blue property world physical donkey pumpkin"

client = Tron(network="nile")

from_ = client.generate_address_from_mnemonic(mnemonic, account_path="m/44'/195'/0'/0/0")["base58check_address"]
balance = client.get_account_balance(from_)
print("my addr: ", from_, "balance: ", balance)
to = input("to: ")
amount = int(input("amount in TRX: "))


def mnemonic_to_private_key():
    seed = seed_from_mnemonic(mnemonic, passphrase="")
    private_key = key_from_seed(seed, account_path="m/44'/195'/0'/0/0")
    return PrivateKey(private_key)


t = client.trx.transfer(from_, to, amount * 1_000_000).build().sign(mnemonic_to_private_key()).broadcast()

print(t.wait())
