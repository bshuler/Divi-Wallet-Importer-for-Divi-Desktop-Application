"""BIP39 mnemonic validation using only Python stdlib."""

import hashlib
from typing import Tuple

from .bip39_wordlist import WORDLIST


def validate_mnemonic(mnemonic: str) -> Tuple[bool, str]:
    """
    Validate a BIP39 mnemonic seed phrase.

    Args:
        mnemonic: Space-separated mnemonic string (12 words expected)

    Returns:
        Tuple of (success: bool, message: str)
        On success: (True, "Mnemonic seed phrase is valid!")
        On failure: (False, error description)
    """
    # Split and normalize
    words = mnemonic.strip().lower().split()

    # Check word count
    if len(words) != 12:
        return (False, 'Mnemonic must be exactly 12 words.')

    # Check each word is in wordlist and get indices
    indices = []
    for i, word in enumerate(words):
        try:
            idx = WORDLIST.index(word)
            indices.append(idx)
        except ValueError:
            return (False, f'Word "{word}" (word {i+1}) is not in the BIP39 wordlist.')

    # Convert indices to 11-bit binary strings and concatenate
    bits = ''.join(format(idx, '011b') for idx in indices)

    # Split into entropy (128 bits) and checksum (4 bits)
    entropy_bits = bits[:128]
    checksum_bits = bits[128:]

    # Convert entropy bits to bytes
    entropy_bytes = bytearray()
    for i in range(16):
        byte_bits = entropy_bits[i * 8:(i + 1) * 8]
        entropy_bytes.append(int(byte_bits, 2))

    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(entropy_bytes).digest()

    # Extract first 4 bits of hash
    hash_bits = format(hash_bytes[0], '08b')[:4]

    # Compare checksums
    if hash_bits != checksum_bits:
        return (False, 'Invalid checksum. Please double-check your seed words.')

    return (True, 'Mnemonic seed phrase is valid!')
