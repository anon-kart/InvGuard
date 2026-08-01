pragma solidity ^0.5.11;

contract Target {

    uint receivers_unchk18;
    address payable addr_unchk18;

    function bug_unchk18() public {
        uint receivers_unchk18;
        address payable addr_unchk18;
        require(addr_unchk18.send(42 ether), "Transfer failed");
        receivers_unchk18 += 1;
    }

    function() external payable {}

    function deposit() public payable {}

}