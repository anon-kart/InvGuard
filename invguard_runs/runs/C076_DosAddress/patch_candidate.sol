pragma solidity ^0.4.24;

contract DosAddress {
    address[] creditorAddresses;
    bool win = false;
    uint256 public constant MAX_CREDITORS = 1750;

    function emptyCreditors() public {
        if (creditorAddresses.length > 1500) {
            creditorAddresses = new address[](0);
            win = true;
        }
    }

    function addCreditors() public returns (bool) {
        require(creditorAddresses.length + 350 <= MAX_CREDITORS);
        for (uint256 i = 0; i < 350; i++) {
            creditorAddresses.push(msg.sender);
        }
        return true;
    }

    function iWin() public view returns (bool) {
        return win;
    }

    function numberCreditors() public view returns (uint256) {
        return creditorAddresses.length;
    }
}
