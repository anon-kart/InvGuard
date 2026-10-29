pragma solidity ^0.4.24;

contract GuessTheRandomNumber {
    constructor() public payable {
        require(msg.value == 1 ether);
    }

    function guess(uint8 n) public payable {
        require(msg.value == 1 ether);
        uint8 answer = uint8(keccak256(abi.encodePacked(blockhash(block.number - 1), now)));
        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}
