import asyncio
import random
import json
import websockets
import base64
from eth_account import Account
from loguru import logger
from primp import AsyncClient
from web3 import AsyncWeb3, Web3
from typing import Dict, Optional, List
from eth_account.messages import encode_defunct
import functools
import time

from src.utils.config import Config
from src.utils.constants import RPC_URL, EXPLORER_URL


def with_retries(func):
    """Decorator to add retry functionality to async methods."""
    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        attempts = getattr(self.config.SETTINGS, 'ATTEMPTS', 5)  # Default to 5 if not set
        pause_range = getattr(self.config.SETTINGS, 'PAUSE_BETWEEN_ATTEMPTS', [5, 15])  # Default to [5, 15] if not set
        last_exception = None
        
        for attempt in range(attempts):
            try:
                return await func(self, *args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"[{self.account_index}] Attempt {attempt + 1}/{attempts} failed for {func.__name__}: {str(e)}")
                if attempt < attempts - 1:  # Don't sleep on the last attempt
                    pause_time = random.uniform(pause_range[0], pause_range[1])
                    logger.info(f"[{self.account_index}] Waiting {pause_time:.2f} seconds before next attempt...")
                    await asyncio.sleep(pause_time)
                
        logger.error(f"[{self.account_index}] All {attempts} attempts failed for {func.__name__}")
        raise last_exception

    return wrapper

class Dusted:
    def __init__(
        self,
        account_index: int,
        proxy: str,
        private_key: str,
        config: Config,
        session: AsyncClient,
    ):
        self.account_index = account_index
        self.proxy = proxy
        self.private_key = private_key
        self.config = config
        self.session = session
        self.auth_token = None
        self.ws_connection = None

        self.account: Account = Account.from_key(private_key=private_key)
        self.web3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(RPC_URL))

    def get_auth_headers(self) -> Dict[str, str]:
        """Get headers with authorization if token is available."""
        headers = {}
        if self.auth_token:
            headers['Authorization'] = f'Bearer {self.auth_token}'
        return headers

    @with_retries
    async def get_gas_params(self) -> Dict[str, int]:
        """Get current gas parameters from the network."""
        latest_block = await self.web3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]
        max_priority_fee = await self.web3.eth.max_priority_fee

        # Calculate maxFeePerGas (base fee + priority fee)
        max_fee = base_fee + max_priority_fee

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    @with_retries
    async def estimate_gas(self, transaction: dict) -> int:
        """Estimate gas for transaction and add some buffer."""
        try:
            estimated = await self.web3.eth.estimate_gas(transaction)
            # Add 10% to estimated gas for safety
            return int(estimated * 1.1)
        except Exception as e:
            logger.warning(
                f"[{self.account_index}] Error estimating gas: {e}. Using default gas limit"
            )
            raise e

    @with_retries
    async def login(self) -> Dict:
        """Login to Dusted service using the signature method."""
        try:
            logger.info(f"[{self.account_index}] Starting Dusted login process")
            
            # Generate current timestamp in ISO format
            current_time = time.strftime('%Y-%m-%dT%H:%M:%S.000Z', time.gmtime())
            logger.debug(f"[{self.account_index}] Generated timestamp: {current_time}")
            
            # Generate a random nonce
            nonce = f"{random.randint(100000, 999999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}-{random.randint(100000000000, 999999999999)}"
            logger.debug(f"[{self.account_index}] Generated nonce: {nonce}")
            
            # Create the message to sign
            message = f"www.dusted.app wants you to sign in with your Ethereum account:\n{self.account.address}\n\nI am proving ownership of the Ethereum account {self.account.address}.\n\nURI: https://www.dusted.app\nVersion: 1\nChain ID: 1\nNonce: {nonce}\nIssued At: {current_time}"
            logger.debug(f"[{self.account_index}] Message to sign: {message}")
            
            # Sign the message
            message_hash = encode_defunct(text=message)
            signature = self.account.sign_message(message_hash)
            signature_hex = signature.signature.hex()
            logger.debug(f"[{self.account_index}] Generated signature: 0x{signature_hex}")
            
            # Prepare the login payload
            json_data = {
                'message': message,
                'signature': f"0x{signature_hex}",
                'provider': 'metamask',
                'chainId': '0x279f',  # Chain ID in hex (10143 in decimal)
            }
            logger.debug(f"[{self.account_index}] Login payload: {json.dumps(json_data, indent=2)}")
            
            logger.info(f"[{self.account_index}] Sending sign-in request to Dusted")
            sign_in_response = await self.session.post(
                f'https://api.xyz.land/signature/evm/{self.account.address}/sign',
                json=json_data
            )
            
            sign_in_data = sign_in_response.json()
            logger.debug(f"[{self.account_index}] Login response: {json.dumps(sign_in_data, indent=2)}")
            
            if 'token' not in sign_in_data:
                raise Exception(f"Failed to sign in: {sign_in_data}")
            
            # Store the auth token
            self.auth_token = sign_in_data['token']
            logger.debug(f"[{self.account_index}] Auth token received: {self.auth_token[:10]}...")
            logger.success(f"[{self.account_index}] Dusted login successful")
            return sign_in_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in Dusted login: {e}")
            raise e

    @with_retries
    async def connect_websocket(self) -> None:
        """Establish WebSocket connection for authentication."""
        try:
            logger.info(f"[{self.account_index}] Establishing WebSocket connection")
            
            # WebSocket connection headers
            headers = {
                'Origin': 'https://www.dusted.app',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
                'Accept-Language': 'en-US,en;q=0.9',
            }
            
            # Connect to the WebSocket server with automatic ping/pong
            self.ws_connection = await websockets.connect(
                'wss://ws.xyz.land/',
                extra_headers=headers,
                ping_interval=30,  # Send ping every 30 seconds
                ping_timeout=10    # Wait 10 seconds for pong response
            )
            logger.success(f"[{self.account_index}] WebSocket connection established")
            
            # Start listening for incoming messages in a separate task
            self.message_queue = asyncio.Queue()
            self.ws_listener_task = asyncio.create_task(self.listen_for_ws_messages())
            
            # Generate device ID matching the website format: device_[timestamp]_[random-9-char-string]
            timestamp = int(time.time() * 1000)  # Current timestamp in milliseconds
            random_string = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=9))
            device_id = f"device_{timestamp}_{random_string}"
            logger.debug(f"[{self.account_index}] Generated device ID: {device_id}")
            
            # Generate browser ID by appending "_browser" to the device ID
            browser_id = f"{device_id}_browser"
            logger.debug(f"[{self.account_index}] Generated browser ID: {browser_id}")
            
            # Create and send the first authentication message
            logger.info(f"[{self.account_index}] Sending WebSocket authentication message")
            
            # Construct the auth content
            auth_content = json.dumps({
                "token": self.auth_token,
                "deviceId": device_id,
                "browserId": browser_id
            })
            
            # Binary prefix for the auth message
            # This prefix is a binary header that the server expects before the actual JSON content
            first_message = b'\x12\xca\x03\x0a\x8e\x02' + auth_content.encode('utf-8')
            
            # Log the message in base64 format for debugging
            base64_message = base64.b64encode(first_message).decode('ascii')
            logger.debug(f"[{self.account_index}] First WebSocket message (base64): {base64_message}")
            
            # Log the message in hex format for binary analysis
            logger.debug(f"[{self.account_index}] First WebSocket message (hex): {first_message.hex()}")
            
            # Log the auth content in UTF-8 format (sanitized version for security)
            auth_content_sanitized = json.dumps({
                "token": self.auth_token[:10] + "..." if self.auth_token else "None",
                "deviceId": device_id,
                "browserId": browser_id
            })
            logger.debug(f"[{self.account_index}] Auth content (sanitized): {auth_content_sanitized}")
            
            # Send the first authentication message
            await self.ws_connection.send(first_message)
            logger.info(f"[{self.account_index}] Authentication message sent, waiting for server response...")
            
            # Very short wait between messages
            await asyncio.sleep(0.2)  # 200ms wait between messages
            
            # Send a second message with a static payload
            second_message = b'\x08\x02\x2a\x00'  # This corresponds to base64 "CAIqAA=="
            
            # Log the second message in base64 format
            base64_second = base64.b64encode(second_message).decode('ascii')
            logger.debug(f"[{self.account_index}] Second WebSocket message (base64): {base64_second}")
            
            # Log the second message in hex format
            logger.debug(f"[{self.account_index}] Second WebSocket message (hex): {second_message.hex()}")
            
            # Send the second message 
            await self.ws_connection.send(second_message)
            logger.info(f"[{self.account_index}] Second message sent, keeping connection open...")
            
            # Start heartbeat mechanism to keep the connection alive
            self.heartbeat_task = asyncio.create_task(self.send_heartbeats())
            logger.info(f"[{self.account_index}] Started heartbeat mechanism")
            
            # We'll keep the connection open and proceed with regular requests
            logger.info(f"[{self.account_index}] WebSocket connection is active and listening for messages")
            logger.info(f"[{self.account_index}] Continuing with regular requests while keeping WebSocket open...")
            
            return
                
        except Exception as e:
            if self.ws_connection and not self.ws_connection.closed:
                try:
                    await self.ws_connection.close()
                except:
                    pass
                self.ws_connection = None
                
            if self.ws_listener_task:
                self.ws_listener_task.cancel()
                try:
                    await self.ws_listener_task
                except asyncio.CancelledError:
                    pass
                self.ws_listener_task = None
                
            if hasattr(self, 'heartbeat_task') and self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                self.heartbeat_task = None
                
            logger.error(f"[{self.account_index}] Error establishing WebSocket connection: {e}")
            raise e

    async def wait_for_response(self):
        """Wait for a response message from the WebSocket server."""
        return await self.message_queue.get()

    async def send_heartbeats(self):
        """Send periodic heartbeats to keep the WebSocket connection alive."""
        try:
            logger.info(f"[{self.account_index}] Starting WebSocket heartbeat mechanism")
            heartbeat_counter = 0
            
            # Simple heartbeat mechanism sending a ping every 25 seconds
            while self.ws_connection and not self.ws_connection.closed:
                await asyncio.sleep(25)
                
                if self.ws_connection and not self.ws_connection.closed:
                    try:
                        heartbeat_counter += 1
                        logger.info(f"[{self.account_index}] Sending WebSocket heartbeat ping #{heartbeat_counter}")
                        
                        pong_waiter = await self.ws_connection.ping()
                        await asyncio.wait_for(pong_waiter, timeout=5)
                        
                        logger.info(f"[{self.account_index}] Received pong response for heartbeat #{heartbeat_counter}")
                    except asyncio.TimeoutError:
                        logger.warning(f"[{self.account_index}] Heartbeat #{heartbeat_counter} timed out - no pong received")
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.warning(f"[{self.account_index}] Cannot send heartbeat #{heartbeat_counter} - connection closed: {e}")
                        break
                    except Exception as e:
                        logger.warning(f"[{self.account_index}] Error in heartbeat #{heartbeat_counter} mechanism: {e}")
                
        except asyncio.CancelledError:
            logger.info(f"[{self.account_index}] WebSocket heartbeat task cancelled after {heartbeat_counter} heartbeats")
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in heartbeat task: {e}")
            
        logger.info(f"[{self.account_index}] WebSocket heartbeat mechanism stopped after {heartbeat_counter} heartbeats")

    async def listen_for_ws_messages(self):
        """Listen for WebSocket messages from the server and log them."""
        try:
            logger.info(f"[{self.account_index}] Starting WebSocket message listener")
            message_counter = 0
            
            while self.ws_connection and not self.ws_connection.closed:
                try:
                    # Wait for incoming message with a timeout
                    message = await asyncio.wait_for(self.ws_connection.recv(), timeout=1.0)
                    message_counter += 1
                    
                    # Add message to the queue for other tasks waiting for responses
                    await self.message_queue.put(message)
                    
                    # Log the message in hex format
                    if isinstance(message, bytes):
                        logger.info(f"[{self.account_index}] ✅ Received WebSocket binary message #{message_counter}")
                        logger.info(f"[{self.account_index}] Message #{message_counter} (hex): {message.hex()}")
                        
                        # Log in base64 format for easier sharing/analysis
                        base64_msg = base64.b64encode(message).decode('ascii')
                        logger.info(f"[{self.account_index}] Message #{message_counter} (base64): {base64_msg}")
                        
                        # Try to decode as UTF-8
                        try:
                            decoded = message.decode('utf-8', errors='replace')
                            logger.info(f"[{self.account_index}] Message #{message_counter} (utf8): {decoded}")
                        except Exception as e:
                            logger.debug(f"[{self.account_index}] Failed to decode message to UTF-8: {e}")
                            
                        # Try to extract any JSON content
                        try:
                            # Skip binary headers, try to find JSON
                            json_start = message.find(b'{')
                            if json_start >= 0:
                                json_text = message[json_start:].decode('utf-8', errors='replace')
                                # Try to parse and pretty print
                                parsed = json.loads(json_text)
                                logger.info(f"[{self.account_index}] Message #{message_counter} contains JSON: {json.dumps(parsed, indent=2)}")
                        except Exception:
                            # Don't log parsing errors as they're expected for binary messages
                            pass
                            
                    else:
                        logger.info(f"[{self.account_index}] ✅ Received WebSocket text message #{message_counter}: {message}")
                        
                        # Try to parse as JSON if it looks like JSON
                        if message.strip().startswith('{') and message.strip().endswith('}'):
                            try:
                                parsed = json.loads(message)
                                logger.info(f"[{self.account_index}] Message #{message_counter} JSON: {json.dumps(parsed, indent=2)}")
                            except:
                                pass
                        
                except asyncio.TimeoutError:
                    # Timeout is normal, just continue the loop
                    continue
                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"[{self.account_index}] WebSocket connection closed by server: {e}")
                    logger.info(f"[{self.account_index}] Connection close code: {e.code}, reason: {e.reason}")
                    break
                except Exception as e:
                    logger.error(f"[{self.account_index}] Error in WebSocket listener: {e}")
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"[{self.account_index}] WebSocket listener task cancelled")
        except Exception as e:
            logger.error(f"[{self.account_index}] WebSocket listener task error: {e}")
        
        logger.info(f"[{self.account_index}] WebSocket message listener stopped after receiving {message_counter} messages")

    async def close_websocket(self) -> None:
        """Close the WebSocket connection."""
        try:
            # Cancel the heartbeat task if it exists
            if hasattr(self, 'heartbeat_task') and self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
                self.heartbeat_task = None
            
            # Cancel the listener task if it exists
            if hasattr(self, 'ws_listener_task') and self.ws_listener_task:
                self.ws_listener_task.cancel()
                try:
                    await self.ws_listener_task
                except asyncio.CancelledError:
                    pass
                self.ws_listener_task = None
                
            if self.ws_connection:
                logger.info(f"[{self.account_index}] Closing WebSocket connection")
                await self.ws_connection.close()
                logger.success(f"[{self.account_index}] WebSocket connection closed")
                self.ws_connection = None
        except Exception as e:
            logger.error(f"[{self.account_index}] Error closing WebSocket connection: {e}")
            # Don't raise the exception, just log it

    @with_retries
    async def get_balance(self) -> Dict:
        """Get user balance and extract user_id and wallet_id."""
        try:
            logger.info(f"[{self.account_index}] Fetching user balance")
            
            balance_response = await self.session.get(
                'https://api.xyz.land/balances',
                headers=self.get_auth_headers()
            )
            
            balance_data = balance_response.json()
            logger.debug(f"[{self.account_index}] Balance response: {json.dumps(balance_data, indent=2)}")
            
            if 'user_id' not in balance_data or 'wallet_address' not in balance_data:
                raise Exception(f"Invalid balance response: {balance_data}")
                
            # Store user_id for later use
            self.user_id = balance_data['user_id']
            
            # Try to find wallet_id in tokens array if it exists
            self.wallet_id = self.user_id  # Default to user_id as fallback
            
            logger.info(f"[{self.account_index}] User ID: {self.user_id}")
            logger.info(f"[{self.account_index}] Wallet address: {balance_data['wallet_address']}")
            
            return balance_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error fetching balance: {e}")
            raise e

    @with_retries
    async def join_room(self) -> Dict:
        """Join the Monad native token room."""
        try:
            logger.info(f"[{self.account_index}] Joining Monad native token room")
            
            json_data = {
                'wallet_id': self.user_id,  # Use user_id as wallet_id
            }
            
            room_response = await self.session.post(
                'https://api.xyz.land/rooms/monad-testnet/native/subscribe',
                headers=self.get_auth_headers(),
                json=json_data
            )
            
            room_data = room_response.json()
            logger.debug(f"[{self.account_index}] Room join response: {json.dumps(room_data, indent=2)}")
            
            if 'message' not in room_data or room_data.get('message') != 'Successfully joined room':
                logger.warning(f"[{self.account_index}] Room join may have failed: {room_data}")
            else:
                logger.success(f"[{self.account_index}] Successfully joined Monad native token room")
                
                # Update wallet_id if it's available in the response
                if 'user' in room_data and 'wallet' in room_data['user'] and 'wallet_id' in room_data['user']['wallet']:
                    self.wallet_id = room_data['user']['wallet']['wallet_id']
                    logger.info(f"[{self.account_index}] Wallet ID: {self.wallet_id}")
            
            return room_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error joining room: {e}")
            raise e

    @with_retries
    async def agree_to_tos(self) -> Dict:
        """Agree to the terms of service."""
        try:
            logger.info(f"[{self.account_index}] Agreeing to terms of service")
            
            json_data = {
                'agreed_tos': True,
            }
            
            tos_response = await self.session.patch(
                'https://api.xyz.land/users/@me',
                headers=self.get_auth_headers(),
                json=json_data
            )
            
            tos_data = tos_response.json()
            logger.debug(f"[{self.account_index}] TOS agreement response: {json.dumps(tos_data, indent=2)}")
            
            if 'message' not in tos_data or tos_data.get('message') != 'updated successfully':
                logger.warning(f"[{self.account_index}] TOS agreement may have failed: {tos_data}")
            else:
                logger.success(f"[{self.account_index}] Successfully agreed to terms of service")
            
            return tos_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error agreeing to TOS: {e}")
            raise e

    @with_retries
    async def claim(self) -> int:
        """Play the lasso game until no plays remain. Returns the total score."""
        try:
            logger.info(f"[{self.account_index}] Starting lasso game")
            
            params = {
                'network': 'monad',
                'chain_id': '10143',
            }
            
            total_plays = 0
            total_score = 0
            
            # Try to play until no more plays remain
            try:
                while True:
                    logger.info(f"[{self.account_index}] Sending lasso play request")
                    
                    response = await self.session.post(
                        'https://api.xyz.land/lasso/play',
                        params=params,
                        headers=self.get_auth_headers()
                    )
                    
                    play_data = response.json()
                    logger.debug(f"[{self.account_index}] Lasso play response: {json.dumps(play_data, indent=2)}")
                    
                    # Check for error response indicating no more plays
                    if 'error' in play_data:
                        error_msg = play_data.get('error')
                        logger.warning(f"[{self.account_index}] Lasso play error: {error_msg}")
                        logger.info(f"[{self.account_index}] Already played all games or other error. Will still try to claim rewards.")
                        break
                    
                    if 'score' not in play_data or 'remainingPlays' not in play_data:
                        logger.warning(f"[{self.account_index}] Invalid lasso play response: {play_data}")
                        break
                    
                    score = play_data['score']
                    remaining_plays = play_data['remainingPlays']
                    
                    total_plays += 1
                    total_score += score
                    
                    logger.success(f"[{self.account_index}] Lasso play #{total_plays} - Score: {score}, Remaining plays: {remaining_plays}")
                    
                    if remaining_plays <= 0:
                        logger.info(f"[{self.account_index}] No more plays remaining. Total plays: {total_plays}, Total score: {total_score}")
                        break
                    
                    # Add a small delay between requests
                    await asyncio.sleep(random.uniform(1, 3))
            except Exception as e:
                logger.warning(f"[{self.account_index}] Error during lasso gameplay: {e}. Will still try to claim rewards.")
            
            if total_plays > 0:
                logger.success(f"[{self.account_index}] Completed all lasso plays with total score: {total_score}")
            else:
                logger.info(f"[{self.account_index}] No lasso plays were completed.")
                
            return total_score
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error in claim method: {e}")
            # Don't raise the exception, return 0 score but still allow claiming
            return 0

    @with_retries
    async def get_lasso_score(self) -> Dict:
        """Get the current lasso score, remaining plays and rank information."""
        try:
            logger.info(f"[{self.account_index}] Fetching lasso score information")
            
            score_response = await self.session.get(
                'https://api.xyz.land/lasso/score',
                headers=self.get_auth_headers()
            )
            
            score_data = score_response.json()
            logger.debug(f"[{self.account_index}] Lasso score response: {json.dumps(score_data, indent=2)}")
            
            if 'remainingPlays' in score_data and 'score' in score_data and 'rank' in score_data:
                logger.info(f"[{self.account_index}] Lasso stats - Score: {score_data['score']}, Rank: {score_data['rank']}, Remaining plays: {score_data['remainingPlays']}")
            else:
                logger.warning(f"[{self.account_index}] Invalid lasso score response format: {score_data}")
                
            return score_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error fetching lasso score: {e}")
            raise e

    @with_retries
    async def get_lasso_leaderboard(self) -> Dict:
        """Get the top scores from the lasso game leaderboard."""
        try:
            logger.info(f"[{self.account_index}] Fetching lasso leaderboard")
            
            params = {
                'network': 'monad',
                'chain_id': '10143',
            }
            
            leaderboard_response = await self.session.get(
                'https://api.xyz.land/lasso/scores',
                params=params,
                headers=self.get_auth_headers()
            )
            
            leaderboard_data = leaderboard_response.json()
            logger.debug(f"[{self.account_index}] Lasso leaderboard response: {json.dumps(leaderboard_data, indent=2)}")
            
            if 'scores' in leaderboard_data and len(leaderboard_data['scores']) > 0:
                top_score = leaderboard_data['scores'][0]
                logger.info(f"[{self.account_index}] Lasso leaderboard - Top score: {top_score['score']} by {top_score['wallet_address']}")
                logger.info(f"[{self.account_index}] Leaderboard contains {len(leaderboard_data['scores'])} players")
            else:
                logger.warning(f"[{self.account_index}] Invalid leaderboard response format or empty leaderboard")
                
            return leaderboard_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error fetching lasso leaderboard: {e}")
            raise e

    @with_retries
    async def check_email_claim(self) -> Dict:
        """Check email claim status before claiming rewards."""
        try:
            logger.info(f"[{self.account_index}] Checking email claim status")
            
            email_claim_response = await self.session.get(
                'https://api.xyz.land/email/claim',
                headers=self.get_auth_headers()
            )
            
            email_claim_data = email_claim_response.json()
            logger.debug(f"[{self.account_index}] Email claim response: {json.dumps(email_claim_data, indent=2)}")
            
            logger.info(f"[{self.account_index}] Email claim check completed")
            return email_claim_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error checking email claim: {e}")
            raise e

    @with_retries
    async def get_user(self) -> Dict:
        """Get user information before claiming rewards."""
        try:
            logger.info(f"[{self.account_index}] Fetching user information")
            
            user_response = await self.session.get(
                'https://api.xyz.land/users/@me',
                headers=self.get_auth_headers()
            )
            
            user_data = user_response.json()
            logger.debug(f"[{self.account_index}] User information response: {json.dumps(user_data, indent=2)}")
            
            if 'wallet' in user_data and 'wallet_id' in user_data['wallet']:
                logger.info(f"[{self.account_index}] User wallet ID: {user_data['wallet']['wallet_id']}")
                
                # Update wallet_id if it's available in the response
                self.wallet_id = user_data['wallet']['wallet_id']
            
            if 'profile' in user_data and 'user_id' in user_data['profile']:
                logger.info(f"[{self.account_index}] User ID: {user_data['profile']['user_id']}")
                
                # Update user_id if it's available in the response
                self.user_id = user_data['profile']['user_id']
            
            logger.info(f"[{self.account_index}] User information check completed")
            return user_data
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error fetching user information: {e}")
            raise e

    @with_retries
    async def claim_rewards(self) -> bool:
        """Claim rewards after playing all games."""
        try:
            logger.info(f"[{self.account_index}] Requesting claim signature")
            
            # Get claim signature
            claim_response = await self.session.get(
                'https://api.xyz.land/lasso/claim',
                headers=self.get_auth_headers()
            )
            
            claim_data = claim_response.json()
            logger.debug(f"[{self.account_index}] Claim response: {json.dumps(claim_data, indent=2)}")
            
            # Check for error in claim response
            if 'error' in claim_data:
                error_msg = claim_data.get('error')
                logger.warning(f"[{self.account_index}] Claim error: {error_msg}")
                # If error indicates no rewards to claim, return gracefully
                if "already claimed" in error_msg.lower() or "no rewards" in error_msg.lower():
                    logger.info(f"[{self.account_index}] No rewards to claim or already claimed")
                    return False
                raise Exception(f"Claim error: {error_msg}")
            
            # Handle "Claim not available" message
            if 'message' in claim_data and claim_data.get('message') == 'Claim not available':
                logger.warning(f"[{self.account_index}] Claim not available yet, retrying...")
                raise Exception("Claim not available yet, will retry")
            
            if 'signature' not in claim_data or 'score' not in claim_data:
                logger.warning(f"[{self.account_index}] Invalid claim response: {claim_data}")
                return False
            
            signature = claim_data['signature']
            score = claim_data['score']
            
            logger.info(f"[{self.account_index}] Received signature for score: {score}")
            
            # Create contract instance
            contract_address = Web3.to_checksum_address("0x18C9534dfe16a0314B66395F48549716FfF9AA66")
            
            # ABI for the claim function
            abi = [
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "totalPoints",
                            "type": "uint256"
                        },
                        {
                            "internalType": "bytes",
                            "name": "signature",
                            "type": "bytes"
                        }
                    ],
                    "name": "claim",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
            
            contract = self.web3.eth.contract(address=contract_address, abi=abi)
            
            # Prepare transaction
            nonce = await self.web3.eth.get_transaction_count(self.account.address)
            gas_params = await self.get_gas_params()
            
            # Convert signature to bytes if it's a string
            if isinstance(signature, str) and signature.startswith("0x"):
                signature_bytes = bytes.fromhex(signature[2:])
            else:
                signature_bytes = bytes.fromhex(signature)
                
            # Build transaction
            tx = await contract.functions.claim(
                score,  # Using the score from the claim response
                signature_bytes
            ).build_transaction({
                'from': self.account.address,
                'nonce': nonce,
                'chainId': 10143,
                **gas_params
            })
            
            # Estimate gas
            try:
                gas_limit = await self.estimate_gas(tx)
                tx['gas'] = gas_limit
            except Exception as e:
                logger.warning(f"[{self.account_index}] Error estimating gas: {e}. Using default gas limit")
                tx['gas'] = 300000  # Default gas limit
                
            # Sign and send transaction
            signed_tx = self.account.sign_transaction(tx)
            tx_hash, receipt = await self.send_and_wait_transaction(signed_tx)
            
            logger.success(f"[{self.account_index}] Successfully claimed rewards for score: {score}")
            return True
            
        except Exception as e:
            logger.error(f"[{self.account_index}] Error claiming rewards: {e}")
            raise e

    @with_retries
    async def send_and_wait_transaction(self, signed_tx) -> tuple:
        """Send transaction and wait for receipt."""
        tx_hash = await self.web3.eth.send_raw_transaction(signed_tx.raw_transaction)
        logger.info(f"[{self.account_index}] Waiting for transaction confirmation...")
        
        receipt = await self.web3.eth.wait_for_transaction_receipt(tx_hash)
        
        if receipt['status'] == 1:
            logger.success(f"[{self.account_index}] Transaction successful! Explorer URL: {EXPLORER_URL}{tx_hash.hex()}")
        else:
            logger.error(f"[{self.account_index}] Transaction failed! Explorer URL: {EXPLORER_URL}{tx_hash.hex()}")
            raise Exception("Transaction failed")
            
        return tx_hash, receipt

    async def execute(self):
        """Main execution function for Dusted platform."""
        try:
            logger.info(f"[{self.account_index}] Starting Dusted execution")
            
            # Initialize user_id and wallet_id
            self.user_id = None
            self.wallet_id = None
            
            # Login to the platform
            await self.login()
            logger.info(f"[{self.account_index}] Login successful")
            
            # Establish WebSocket connection after login
            await self.connect_websocket()
            logger.info(f"[{self.account_index}] WebSocket connection established and will remain open during execution")
            
            # Get user balance to fetch user_id
            await self.get_balance()
            
            # Join Monad native token room
            await self.join_room()
            
            # Agree to terms of service
            await self.agree_to_tos()
            
            # Play the lasso game (will handle errors gracefully)
            total_score = await self.claim()
            
            # Add a delay before claiming rewards to allow backend processing
            delay = random.uniform(5, 8)
            logger.info(f"[{self.account_index}] Waiting {delay:.2f} seconds before claiming rewards...")
            await asyncio.sleep(delay)
            
            # Get score information before claiming
            await self.get_lasso_score()
            
            # Always try to claim rewards, regardless of whether games were played
            claim_result = await self.claim_rewards()
            
            # Wait some time to observe any final WebSocket responses
            logger.info(f"[{self.account_index}] Execution completed, waiting 10 seconds for any final WebSocket messages...")
            await asyncio.sleep(10)
            
            # Finally close the WebSocket connection
            logger.info(f"[{self.account_index}] Closing WebSocket connection...")
            await self.close_websocket()
            
            logger.success(f"[{self.account_index}] Dusted execution completed successfully")
            return True

        except Exception as e:
            # Make sure to close WebSocket connection even if there's an error
            logger.error(f"[{self.account_index}] Error in Dusted execute: {e}")
            
            if hasattr(self, 'ws_connection') and self.ws_connection:
                logger.info(f"[{self.account_index}] Closing WebSocket connection due to error...")
                await self.close_websocket()
                
            return False
    

