/*
 * @source: https://capturetheether.com/challenges/lotteries/guess-the-random-number/
 * @author: Steve Marx
 */

pragma solidity ^0.4.21;

contract GuessTheRandomNumberChallenge {
    mapping(address => bytes32) private commitments;
    mapping(address => uint256) private commitmentBlocks;

    function GuessTheRandomNumberChallenge() public payable {
        require(msg.value == 1 ether);
    }

    function commit(bytes32 commitment) public payable {
        require(msg.value == 1 ether);
        require(commitment != bytes32(0));
        require(commitments[msg.sender] == bytes32(0) || block.number > commitmentBlocks[msg.sender] + 256);
        require(address(this).balance >= 2 ether);

        commitments[msg.sender] = commitment;
        commitmentBlocks[msg.sender] = block.number;
    }

    function isComplete() public view returns (bool) {
        return address(this).balance == 0;
    }

    function guess(uint8 n, bytes32 salt) public {
        require(commitments[msg.sender] != bytes32(0));
        require(block.number > commitmentBlocks[msg.sender]);
        require(block.number <= commitmentBlocks[msg.sender] + 256);
        require(commitments[msg.sender] == keccak256(msg.sender, n, salt));

        bytes32 randomSource = block.blockhash(commitmentBlocks[msg.sender]);
        uint8 answer = uint8(keccak256(randomSource, msg.sender, salt));

        delete commitments[msg.sender];
        delete commitmentBlocks[msg.sender];

        if (n == answer) {
            msg.sender.transfer(2 ether);
        }
    }
}
