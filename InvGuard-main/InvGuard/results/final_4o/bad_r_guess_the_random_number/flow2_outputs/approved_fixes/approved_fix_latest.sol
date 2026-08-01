/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 * @vulnerable_at_lines: 15
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;
    bytes32 public commitHash;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
    }

    function commit(bytes32 _commitHash) public {
        commitHash = _commitHash;
    }

    function reveal(uint8 _answer, bytes32 _nonce) public {
        require(keccak256(_answer, _nonce) == commitHash);
        answer = _answer;
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function guess(uint8 n) public payable {
        require(msg.value == 1 ether);

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}