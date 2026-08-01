/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_address.sol
 * @author: -
 * @vulnerable_at_lines: 16,17,18
 */

pragma solidity ^0.4.25;

contract DosGas {

    mapping(address => uint) public balances;
    bool win = false;

    function emptyCreditors() public {
        require(msg.sender == address(this)); // Access control
        // Removed the loop to prevent gas limit issues
        win = true;
    }

    function addCreditors() public returns (bool) {
        for(uint i = 0; i < 350; i++) {
            balances[msg.sender] += 1; // Record amounts owed directly
        }
        return true;
    }

    function withdraw() public {
        uint amount = balances[msg.sender];
        require(amount > 0, "No funds to withdraw");
        balances[msg.sender] = 0; // Update state before external call
        require(msg.sender.send(amount)); // Ensure transfer success
    }

    function iWin() public view returns (bool) {
        return win;
    }
}