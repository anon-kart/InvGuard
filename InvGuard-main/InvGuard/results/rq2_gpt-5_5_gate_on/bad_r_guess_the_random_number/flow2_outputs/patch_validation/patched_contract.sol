/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 * @vulnerable_at_lines: 15
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;
    mapping(address => bytes32) private commitments;
    mapping(address => uint256) private commitmentBlocks;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
        // <yes> <report> BAD_RANDOMNESS
        answer = uint8(keccak256(block.blockhash(block.number - 1), now));
    }

    function commit(bytes32 commitment) public {
        require(commitment != bytes32(0));
        require(commitments[msg.sender] == bytes32(0));

        commitments[msg.sender] = commitment;
        commitmentBlocks[msg.sender] = block.number;
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function guess(uint8 n) public payable {
        require(msg.value == 1 ether);
        require(commitments[msg.sender] != bytes32(0));
        require(block.number > commitmentBlocks[msg.sender]);
        require(commitments[msg.sender] == keccak256(msg.sender, n));

        delete commitments[msg.sender];
        delete commitmentBlocks[msg.sender];

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}