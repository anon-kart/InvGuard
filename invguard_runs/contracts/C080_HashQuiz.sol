pragma solidity ^0.8.20;

contract HashQuiz {
    bytes32 public answerHash;

    constructor(bytes32 h) payable {
        answerHash = h;
    }

    function solve(string calldata answer) external {
        require(keccak256(abi.encodePacked(answer)) == answerHash, "wrong");
        payable(msg.sender).transfer(address(this).balance);
    }
}
