pragma solidity ^0.8.20;

contract PayeeRegistry {
    address[] public payees;
    mapping(address => uint256) public owed;

    function register() external payable {
        require(msg.value > 0, "zero");
        if (owed[msg.sender] == 0) {
            payees.push(msg.sender);
        }
        owed[msg.sender] += msg.value;
    }

    function claim() external {
        for (uint256 i = 0; i < payees.length; i++) {
            if (payees[i] == msg.sender) {
                uint256 amt = owed[msg.sender];
                (bool ok, ) = msg.sender.call{value: amt}("");
                require(ok, "send failed");
                owed[msg.sender] = 0;
            }
        }
    }
}
