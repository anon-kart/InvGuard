pragma solidity ^0.8.20;

contract SignedDrop {
    address public signer;
    mapping(address => uint256) public claimed;
    mapping(bytes32 => bool) public used;

    constructor(address s) payable {
        signer = s;
    }

    function claim(uint256 amount, uint8 v, bytes32 r, bytes32 s) external {
        bytes32 digest = keccak256(abi.encodePacked("\x19Ethereum Signed Message:\n32", keccak256(abi.encodePacked(msg.sender, amount))));
        require(!used[digest], "used");
        require(ecrecover(digest, v, r, s) == signer, "sig");
        used[digest] = true;
        claimed[msg.sender] += amount;
        payable(msg.sender).transfer(amount);
    }
}
