pragma solidity ^0.8.20;

interface IMintReceiver {
    function onMint(address operator, uint256 id) external returns (bytes4);
}

contract NFTDrop {
    uint256 public constant MAX_PER_WALLET = 2;
    uint256 public totalMinted;
    mapping(address => uint256) public mintedBy;
    mapping(uint256 => address) public ownerOf;

    function mint() external {
        require(mintedBy[msg.sender] < MAX_PER_WALLET, "limit");
        mintedBy[msg.sender] += 1;
        uint256 id = ++totalMinted;
        ownerOf[id] = msg.sender;
        if (msg.sender.code.length > 0) {
            require(IMintReceiver(msg.sender).onMint(msg.sender, id) == IMintReceiver.onMint.selector, "rejected");
        }
    }
}
