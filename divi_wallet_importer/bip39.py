"""BIP39 mnemonic validation using only Python stdlib."""

import hashlib
from typing import Tuple

from .bip39_wordlist import WORDLIST


def validate_mnemonic(mnemonic: str) -> Tuple[bool, str]:
    """
    Validate a BIP39 mnemonic seed phrase (12 or 24 words).

    Args:
        mnemonic: Space-separated mnemonic string (12 or 24 words)

    Returns:
        Tuple of (success: bool, message: str)
        On success: (True, "Mnemonic seed phrase is valid!")
        On failure: (False, error description)
    """
    # Split and normalize
    words = mnemonic.strip().lower().split()

    # Check word count — BIP39 supports 12, 15, 18, 21, 24 but we accept 12 or 24
    if len(words) not in (12, 24):
        return (False, 'Mnemonic must be 12 or 24 words (got {}).'.format(len(words)))

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

    # BIP39: entropy bits = word_count * 11 - checksum_bits
    # checksum_bits = entropy_bits / 32
    # 12 words: 128 entropy + 4 checksum = 132 bits
    # 24 words: 256 entropy + 8 checksum = 264 bits
    total_bits = len(words) * 11
    checksum_len = total_bits // 33  # CS = ENT / 32, and ENT = total - CS, so CS = total / 33
    entropy_len = total_bits - checksum_len
    entropy_bytes_count = entropy_len // 8

    entropy_bits = bits[:entropy_len]
    checksum_bits = bits[entropy_len:]

    # Convert entropy bits to bytes
    entropy_bytes = bytearray()
    for i in range(entropy_bytes_count):
        byte_bits = entropy_bits[i * 8:(i + 1) * 8]
        entropy_bytes.append(int(byte_bits, 2))

    # Compute SHA-256 hash
    hash_bytes = hashlib.sha256(entropy_bytes).digest()

    # Extract checksum from hash
    hash_bits = ''.join(format(b, '08b') for b in hash_bytes)[:checksum_len]

    # Compare checksums
    if hash_bits != checksum_bits:
        return (False, 'Invalid checksum. Please double-check your seed words.')

    return (True, 'Mnemonic seed phrase is valid!')
