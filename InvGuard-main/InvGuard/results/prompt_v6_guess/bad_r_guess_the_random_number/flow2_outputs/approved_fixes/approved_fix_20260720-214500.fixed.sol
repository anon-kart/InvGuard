/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 * @vulnerable_at_lines: 15
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;
    uint256 public revealBlock;
    bytes32 private commit;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
        commit = keccak256(msg.sender, now); // Commit to the guess
        revealBlock = block.number + 1; // Set the block number for reveal
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function reveal(uint8 n) public {
        require(block.number > revealBlock); // Ensure it's after the reveal block
        require(keccak256(msg.sender, now) == commit); // Check the commitment

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}