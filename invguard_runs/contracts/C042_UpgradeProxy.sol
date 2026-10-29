pragma solidity ^0.8.20;

contract UpgradeProxy {
    address public admin;
    address public implementation;

    constructor(address impl) {
        admin = msg.sender;
        implementation = impl;
    }

    function upgradeTo(address newImpl) external {
        implementation = newImpl;
    }

    fallback() external payable {
        address impl = implementation;
        (bool ok, bytes memory ret) = impl.delegatecall(msg.data);
        require(ok, "delegate failed");
        assembly {
            return(add(ret, 32), mload(ret))
        }
    }

    receive() external payable {}
}
