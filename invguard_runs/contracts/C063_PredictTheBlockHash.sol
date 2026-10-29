pragma solidity ^0.4.24;

contract PredictTheBlockHash {
    struct Guess {
        uint256 blockNumber;
        bytes32 guess;
    }

    mapping(address => Guess) public guesses;

    constructor() public payable {
        require(msg.value == 1 ether);
    }

    function lockInGuess(bytes32 hash) public payable {
        require(guesses[msg.sender].blockNumber == 0);
        require(msg.value == 1 ether);
        guesses[msg.sender].guess = hash;
        guesses[msg.sender].blockNumber = block.number + 1;
    }

    function settle() public {
        require(block.number > guesses[msg.sender].blockNumber);
        bytes32 answer = blockhash(guesses[msg.sender].blockNumber);
        guesses[msg.sender].blockNumber = 0;
        if (guesses[msg.sender].guess == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}
