TESTNET_BRIDGE_RPCS = {
    "Arbitrum": "https://rpc.ankr.com/arbitrum",
    "Optimism": "https://rpc.ankr.com/optimism",
    "Sepolia": "https://sepolia.drpc.org",
}

TESTNET_BRIDGE_EXPLORERS = {
    "Arbitrum": "https://arbiscan.io/tx/0x",
    "Optimism": "https://optimistic.etherscan.io/tx/0x",
}   

TESTNET_BRIDGE_ADDRESS = {
    "Arbitrum": "0xfcA99F4B5186D4bfBDbd2C542dcA2ecA4906BA45",
    "Optimism": "0x8352C746839699B1fc631fddc0C3a00d4AC71A17",
}

TESTNET_BRIDGE_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amountIn", "type": "uint256"},
            {"internalType": "uint256", "name": "amountOutMin", "type": "uint256"},
            {"internalType": "uint16", "name": "dstChainId", "type": "uint16"},
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "address payable", "name": "refundAddress", "type": "address"},
            {"internalType": "address", "name": "zroPaymentAddress", "type": "address"},
            {"internalType": "bytes", "name": "adapterParams", "type": "bytes"}
        ],
        "name": "swapAndBridge",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

