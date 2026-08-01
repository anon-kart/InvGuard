/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 * @vulnerable_at_lines: 15
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;
    uint256 public revealBlock;
    bytes32 public commit;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
        answer = uint8(keccak256(block.blockhash(block.number - 1), now));
        revealBlock = block.number + 1; // Set the block number for reveal
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function commitGuess(bytes32 _commit) public {
        commit = _commit;
    }

    function revealGuess(uint8 n) public {
        require(block.number > revealBlock);
        require(keccak256(n) == commit);

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}