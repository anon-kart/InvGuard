pragma solidity ^0.4.24;

contract Bank {
    function supportsToken() external returns (bytes32);
}

contract NuTokenAirdrop {
    mapping(address => uint256) public tokenBalance;

    function getBalance(address a) public view returns (uint256) {
        return tokenBalance[a];
    }

    modifier supportsToken() {
        require(keccak256(abi.encodePacked("Nu Token")) == Bank(msg.sender).supportsToken());
        _;
    }

    modifier hasNoBalance() {
        require(tokenBalance[msg.sender] == 0);
        _;
    }

    function airDrop() public hasNoBalance supportsToken {
        tokenBalance[msg.sender] += 20;
    }
}
