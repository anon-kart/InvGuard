pragma solidity ^0.8.20;

contract CommitReveal {
    mapping(address => bytes32) public commitments;
    mapping(address => uint256) public commitBlock;

    constructor() payable {}

    function commit(bytes32 c) external payable {
        require(msg.value == 0.1 ether, "fee");
        require(commitBlock[msg.sender] == 0, "pending");
        commitments[msg.sender] = c;
        commitBlock[msg.sender] = block.number;
    }

    function reveal(uint256 guess, bytes32 salt) external {
        uint256 b = commitBlock[msg.sender];
        require(b != 0 && block.number > b + 1 && block.number <= b + 250, "window");
        require(keccak256(abi.encodePacked(guess, salt)) == commitments[msg.sender], "commit");
        commitBlock[msg.sender] = 0;
        uint256 answer = uint256(keccak256(abi.encodePacked(blockhash(b + 1), msg.sender))) % 10;
        if (guess == answer) {
            payable(msg.sender).transfer(0.5 ether);
        }
    }
}
