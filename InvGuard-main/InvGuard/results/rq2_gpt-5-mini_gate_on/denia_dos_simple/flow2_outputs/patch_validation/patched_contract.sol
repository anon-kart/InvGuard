/*
 * @source: https://github.com/SmartContractSecurity/SWC-registry/blob/master/test_cases/dos_gas_limit/dos_simple.sol
 * @author: -
 * @vulnerable_at_lines: 17,18
 */


pragma solidity ^0.4.25;

contract DosOneFunc {

    address[] listAddresses;

    // New: track owed amounts (pull-payment style). Unit: wei
    mapping(address => uint256) public balances;

    // Reentrancy mutex as required
    bool private _locked;

    function ifillArray() public returns (bool){
        require(!_locked);
        _locked = true;

        if(listAddresses.length<1500) {
            // Converted from push-loop to pull-payment pattern:
            // Instead of pushing msg.sender multiple times (which could DoS),
            // record an owed amount for msg.sender and grow the array length
            // in a single, constant-time operation to preserve similar semantics.
            balances[msg.sender] += 350;

            // increase the array length without iterating (fills with zero-addresses)
            uint256 newLen = listAddresses.length + 350;
            listAddresses.length = newLen;

            _locked = false;
            return true;

        } else {
            listAddresses = new address[](0);
            _locked = false;
            return false;
        }
    }

    // Allow users to withdraw their recorded owed amounts (pull-payment).
    function withdraw() public {
        require(!_locked);
        _locked = true;

        uint256 amount = balances[msg.sender];
        require(amount > 0);

        // Effects
        balances[msg.sender] = 0;

        // Interaction: send funds to caller, ensure failure reverts
        require(msg.sender.send(amount));

        _locked = false;
    }
}