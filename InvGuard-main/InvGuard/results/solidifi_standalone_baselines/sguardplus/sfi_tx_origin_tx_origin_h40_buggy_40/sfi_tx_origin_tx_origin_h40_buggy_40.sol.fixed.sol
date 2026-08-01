pragma solidity ^0.5.0;

                        contract sGuardPlus {
                                constructor() internal {
                                        
                                        
                                }
                                
                                
                                
                                
                        }
                contract Target  {
address  public   owner;
constructor () public  {
owner=msg.sender;
}

function sendto_txorigin17 (address payable   receiver,uint    amount,address    owner_txorigin17) public  {
require(msg.sender==owner_txorigin17);
receiver.transfer(amount);
}

function () external payable {
}

function deposit () public payable {
}

}
