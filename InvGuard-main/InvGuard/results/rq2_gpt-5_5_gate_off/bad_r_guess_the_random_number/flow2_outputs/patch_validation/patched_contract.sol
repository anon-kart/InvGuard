/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 * @vulnerable_at_lines: 15
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    uint8 answer;
    address randomnessSource;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
        randomnessSource = msg.sender;
        // <yes> <report> BAD_RANDOMNESS
        answer = uint8(keccak256(block.blockhash(block.number - 1), now));
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function guess(uint8 n) public payable {
        require(msg.value == 1 ether);
        require(msg.data.length >= 164);

        bytes32 randomness;
        uint8 v;
        bytes32 r;
        bytes32 s;

        assembly {
            randomness := calldataload(36)
            v := and(calldataload(68), 0xff)
            r := calldataload(100)
            s := calldataload(132)
        }

        bytes32 signedMessage = keccak256(address(this), msg.sender, n, randomness);
        require(ecrecover(signedMessage, v, r, s) == randomnessSource);

        uint8 winningNumber = uint8(keccak256(randomness, address(this), msg.sender));

        if (n == winningNumber) {
            msg.sender.transfer(2 ether);
        }
    }
}