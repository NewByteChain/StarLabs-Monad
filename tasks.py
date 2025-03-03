TASKS = [
    "FULL_TASK",
]


FAUCET = [
    "faucet",
]

BRIDGE_AND_SWAPS = [
    "memebridge",
    ("izumi", "ambient", "bean", "swaps"),
    "collect_all_to_monad",
]


FULL_TASK = [
    ("izumi", "aircraft", "lilchogstars", "bean", "swaps"),
    ["ambient", "izumi", "bean"],
    ["apriori", "magma", "shmonad"],
    ["magiceden", "monadking"],
    "collect_all_to_monad",
    "logs",
]

BRIDGE_SEPOLIA_AND_CONVERT_TO_MON = [
    "testnet_bridge",
    "orbiter",
    "collect_all_to_monad",
]

CUSTOM_TASK = [
    "",
]

# FAUCETS
# "faucet" - get tokens from faucet
# "farm_faucet" - get tokens from faucet ON FARM ACCOUNTS (data/keys_for_faucet.txt)
# "disperse_farm_accounts" - disperse tokens from farm accounts to main accounts | keys_for_faucet.txt -> private_keys.txt
# "disperse_from_one_wallet" - disperse tokens from one wallet to all other wallets | keys_for_faucet.txt (first wallet) -> private_keys.txt

# SWAPS
# "collect_all_to_monad" - swap all tokens to native token (MON)
# "swaps" - testnet.monad.xyz/ page token swaps
# "bean" - swap tokens on Bean DEX
# "ambient" - swap tokens on Ambient DEX
# "izumi" - swap tokens on Izumi DEX

# STAKES
# "apriori" - stake MON token
# "magma" - stake MON token on Magma
# "shmonad" - buy and stake shmon on shmonad.xyz | LOOK SETTINGS BELOW
# "kintsu" - stake MON token on kintsu.xyz/

# MINT
# "magiceden" - mint NFT on magiceden.io
# "accountable" - mint accountable nft
# "owlto" - deploy contract on Owlto
# "lilchogstars" - mint NFT on testnet.lilchogstars.com/
# "demask" - mint NFT on app.demask.finance/launchpad/0x2cdd146aa75ffa605ff7c5cc5f62d3b52c140f9c/0
# "monadking" - mint NFT on nerzo.xyz/monadking
# "monadking_unlocked" - mint NFT on www.nerzo.xyz/unlocked

# REFUEL
# "gaszip" - gaszip refuel from arbitrum, optimism, base to monad
# "orbiter" - bridge ETH from Sepolia to Monad via Orbiter
# "memebridge" - memebridge refuel from arbitrum, optimism, base to monad

# OTHER
# "logs" - show logs: MON balance | number of transactions | avarage balance | avarage number of transactions
# "nad_domains" - register random domain on nad.domains
# "aircraft" - mint NFT on aircraft.fun