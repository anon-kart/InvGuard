pragma solidity ^0.4.24;

contract BatchPayer {
    address public owner;
    mapping(address => uint256) public pending;
    address[] public recipients;

    constructor() public {
        owner = msg.sender;
    }

    function add(address r) public payable {
        require(msg.value > 0);
        if (pending[r] == 0) {
            recipients.push(r);
        }
        pending[r] += msg.value;
    }

    function payAll() public {
        for (uint256 i = 0; i < recipients.length; i++) {
            address r = recipients[i];
            uint256 amt = pending[r];
            pending[r] = 0;
            if (!r.send(amt)) {
                pending[r] = amt;
            }
        }
    }
}
