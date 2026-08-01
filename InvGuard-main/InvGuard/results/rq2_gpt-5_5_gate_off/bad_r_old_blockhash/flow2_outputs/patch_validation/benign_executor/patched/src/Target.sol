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

    constructor() public payable {
        require(msg.value == 1 ether);
    }

    function lockInGuess(bytes32 hash) public payable {
        require(guesses[msg.sender].block == 0);
        require(msg.value == 1 ether);

        guesses[msg.sender].guess = hash;
        guesses[msg.sender].block  = block.number + 1;
    }

    function settle() public {
        require(guesses[msg.sender].block != 0);
        require(block.number > guesses[msg.sender].block);
        require(block.number <= guesses[msg.sender].block + 256);

        bytes32 answer = blockhash(guesses[msg.sender].block);
        bytes32 userGuess = guesses[msg.sender].guess;

        guesses[msg.sender].block = 0;
        guesses[msg.sender].guess = bytes32(0);

        if (userGuess == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}


// ---- auto-added by BenignExecutor ----
// Provides a stable deployable name used by the harness: `Target`.
// Assumes `PredictTheBlockHashChallenge` has a no-arg constructor (or implicit constructor).
contract Target is PredictTheBlockHashChallenge {
    constructor() PredictTheBlockHashChallenge() {}
}
