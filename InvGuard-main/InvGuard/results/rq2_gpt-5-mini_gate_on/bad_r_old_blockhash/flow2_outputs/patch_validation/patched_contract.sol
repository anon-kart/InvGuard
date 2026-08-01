/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/weak_randomness/old_blockhash.sol
 * @author: -
 * @vulnerable_at_lines: 35
 */

pragma solidity ^0.4.24;

//Based on the the Capture the Ether challange at https://capturetheether.com/challenges/lotteries/predict-the-block-hash/
//Note that while it seems to have a 1/2^256 chance you guess the right hash, actually blockhash returns zero for blocks numbers that are more than 256 blocks ago so you can guess zero and wait.
contract PredictTheBlockHashChallenge {

    struct guess{
      uint block;
      bytes32 guess;
    }

    mapping(address => guess) guesses;

    // Commit-reveal storage for added protection
    mapping(address => bytes32) public revealedSecrets;
    mapping(address => uint) public revealedAt;

    // Reentrancy mutex
    bool private _locked;

    constructor() public payable {
        require(msg.value == 1 ether);
    }

    function lockInGuess(bytes32 hash) public payable {
        require(guesses[msg.sender].block == 0);
        require(msg.value == 1 ether);

        guesses[msg.sender].guess = hash;
        guesses[msg.sender].block  = block.number + 1;
    }

    // New: reveal the preimage of the committed hash. Must be revealed before the target block.
    function revealSecret(bytes32 secret) public {
        // must have an active guess
        require(guesses[msg.sender].block != 0);
        // revelation must occur before the guessed block is mined
        require(block.number < guesses[msg.sender].block);
        // secret must match the committed hash
        require(keccak256(abi.encodePacked(secret)) == guesses[msg.sender].guess);

        revealedSecrets[msg.sender] = secret;
        revealedAt[msg.sender] = block.number;
    }

    function settle() public {
        require(!_locked);
        _locked = true;

        require(block.number > guesses[msg.sender].block);
        // require that the caller revealed a secret and that it was revealed before the guessed block
        require(revealedAt[msg.sender] != 0);
        require(revealedAt[msg.sender] < guesses[msg.sender].block);

        // use both the blockhash and the revealed secret to derive randomness;
        // because the secret had to be revealed before the guessed block, the caller could not compute the outcome in the same block as settle
        bytes32 answer = blockhash(guesses[msg.sender].block);
        bytes32 random = keccak256(abi.encodePacked(answer, revealedSecrets[msg.sender]));

        // clear state BEFORE any external call (CEI) and to prevent reuse
        guesses[msg.sender].block = 0;
        // keep the original committed value in guesses[msg.sender].guess (optional), but clear revealed data
        revealedSecrets[msg.sender] = bytes32(0);
        revealedAt[msg.sender] = 0;

        // simple payout condition derived from the combined randomness (e.g., 50% win chance)
        if (uint256(random) % 2 == 0) {
            msg.sender.transfer(2 ether);
        }

        _locked = false;
    }
}